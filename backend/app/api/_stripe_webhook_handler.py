"""
_stripe_webhook_handler — Single source of truth para processamento Stripe (Tier 2.3.1.1).

Modulo unificado que substitui as 2 implementacoes paralelas (auth.py + billing.py).
Ambas as routes (/api/auth/webhook/stripe e /api/payments/webhook) viram thin
proxies que apenas validam signature e delegam para dispatch_stripe_event().

Logica fundida (best-of-both):
  - Idempotency check via StripeEvent table (de auth.py)
  - Real Stripe period via stripe.Subscription.retrieve (de billing.py)
  - Real amount via session.amount_total + fallback chain de 3 niveis
  - Addon clients merged (slots + flag pra dupla idempotency)
  - persist_invoice_payment (Tier 2.3.1)
  - Sentry capture_exception em falhas criticas (fiscal data)
  - WebhookHit record (auditoria + telemetria por rota pra deprecation futura)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de acesso defensivo (Stripe Event funciona como dict OU object)
# ---------------------------------------------------------------------------

def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Acessa atributo com fallback dict/object. Stripe objects suportam ambos."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _get_metadata(obj: Any) -> dict[str, Any]:
    """Extrai metadata do session/invoice — sempre retorna dict."""
    md = _get_attr(obj, "metadata")
    if md is None:
        return {}
    if isinstance(md, dict):
        return md
    # Stripe metadata pode ser dict-like object
    try:
        return dict(md)
    except (TypeError, ValueError):
        return {}


def _resolve_customer_id(obj: Any) -> str | None:
    """Extrai customer_id (pode vir como str ou objeto expandido)."""
    customer = _get_attr(obj, "customer")
    if customer is None:
        return None
    if isinstance(customer, str):
        return customer
    return _get_attr(customer, "id")


# ---------------------------------------------------------------------------
# Validacao de webhook signature (extraido de auth.py + billing.py — duplicado antes)
# ---------------------------------------------------------------------------

def validate_and_parse_webhook(payload: bytes, sig_header: str) -> Any:
    """Valida assinatura Stripe e retorna evento parseado.

    Levanta ValueError em payload invalido, SignatureVerificationError em
    assinatura invalida — caller route decide HTTP status (400 em ambos).
    """
    import os
    import stripe

    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        # Sem secret, modo dev: parseia sem validar (NAO deve acontecer em prod)
        import json as _json
        logger.warning("STRIPE_WEBHOOK_SECRET nao configurado — parseando sem validacao!")
        try:
            data = _json.loads(payload)
            return stripe.Event.construct_from(data, stripe.api_key)
        except Exception as e:
            raise ValueError(f"payload invalido sem secret: {e}")

    return stripe.Webhook.construct_event(payload, sig_header, secret)


# ---------------------------------------------------------------------------
# Resolvers de dados Stripe (com fallbacks defensivos)
# ---------------------------------------------------------------------------

def _resolve_subscription_period(stripe_sub_id: str | None) -> tuple[datetime, datetime, str]:
    """Resolve (period_start, period_end, source) via stripe.Subscription.retrieve.

    Prioridade contabil: dados reais do Stripe API > estimativa local.

    source values:
      "stripe_api"           → API call OK, datas autenticas
      "fallback_30d_estimate" → API falhou ou stripe_sub_id None, now+30d
    """
    if not stripe_sub_id:
        now = datetime.now(timezone.utc)
        return now, now + timedelta(days=30), "fallback_30d_estimate"

    try:
        import stripe
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
        ps_ts = stripe_sub.get("current_period_start") if isinstance(stripe_sub, dict) else getattr(stripe_sub, "current_period_start", None)
        pe_ts = stripe_sub.get("current_period_end") if isinstance(stripe_sub, dict) else getattr(stripe_sub, "current_period_end", None)
        if ps_ts and pe_ts:
            return (
                datetime.fromtimestamp(int(ps_ts), tz=timezone.utc),
                datetime.fromtimestamp(int(pe_ts), tz=timezone.utc),
                "stripe_api",
            )
    except Exception as e:
        logger.warning(f"stripe.Subscription.retrieve falhou pra {stripe_sub_id}: {e}")
        # Sentry capture: falha ao resolver dado contabil real eh observavel
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except Exception:
            pass

    now = datetime.now(timezone.utc)
    return now, now + timedelta(days=30), "fallback_30d_estimate"


def _resolve_amount(session_obj: Any, stripe_sub_id: str | None, plan: str) -> float:
    """Resolve amount em BRL com chain de 3 niveis (prioridade contabil):

    1. session.amount_total (real charged neste checkout — fonte mais autentica)
    2. stripe.Subscription.retrieve().items[0].price.unit_amount (price real do plano)
    3. PLANS[plan].price (hardcoded local — pode dessincronizar com Stripe Dashboard)
    """
    # Nivel 1: amount_total da session
    amount_total = _get_attr(session_obj, "amount_total")
    if amount_total:
        try:
            return float(amount_total) / 100.0
        except (TypeError, ValueError):
            pass

    # Nivel 2: price.unit_amount do item da subscription
    if stripe_sub_id:
        try:
            import stripe
            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
            items_data = []
            if isinstance(stripe_sub, dict):
                items_data = stripe_sub.get("items", {}).get("data", []) or []
            else:
                items = getattr(stripe_sub, "items", None)
                if items:
                    items_data = getattr(items, "data", []) or []
            if items_data:
                first = items_data[0]
                price = first.get("price") if isinstance(first, dict) else getattr(first, "price", None)
                if price:
                    unit_amount = price.get("unit_amount") if isinstance(price, dict) else getattr(price, "unit_amount", None)
                    if unit_amount:
                        return float(unit_amount) / 100.0
        except Exception as e:
            logger.debug(f"price.unit_amount fallback falhou: {e}")

    # Nivel 3: PLANS dict local
    try:
        from app.api.auth import PLANS as _PLANS
        return float(_PLANS.get(plan, {}).get("price", 0))
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Handlers por event_type (chamados a partir de dispatch_stripe_event)
# ---------------------------------------------------------------------------

def _handle_checkout_session_completed(event: Any, db: Any) -> dict[str, Any]:
    """Processa checkout.session.completed — addon_clients OU nova subscription."""
    from database.models import User, Subscription

    session_obj = _get_attr(event, "data") or {}
    session_obj = _get_attr(session_obj, "object") or session_obj
    if hasattr(event, "data"):
        session_obj = event.data.object

    metadata = _get_metadata(session_obj)
    user_id_str = metadata.get("user_id")
    raw_plan = metadata.get("plan", "free") or "free"
    addon_type = metadata.get("addon_type")

    if not user_id_str:
        return {"status": "skipped", "reason": "no user_id in metadata"}

    try:
        user_id = int(user_id_str)
    except (TypeError, ValueError):
        return {"status": "skipped", "reason": f"invalid user_id: {user_id_str}"}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"status": "skipped", "reason": f"user {user_id} not found"}

    # Caminho ADDON — extra_clients
    if addon_type == "extra_clients":
        # Idempotency primaria: flag em User
        if getattr(user, "addon_clients_purchased", False):
            return {"status": "already_processed", "addon": "extra_clients"}

        slots_str = metadata.get("slots") or metadata.get("extra_clients") or "10"
        try:
            slots = int(slots_str)
        except (TypeError, ValueError):
            slots = 10
        current_extra = user.extra_client_slots or 0
        user.extra_client_slots = current_extra + slots
        user.addon_clients_purchased = True
        cust = _resolve_customer_id(session_obj)
        if cust:
            user.stripe_customer_id = cust
        db.commit()
        logger.info(f"Addon clientes: User {user_id} → +{slots} slots (total: {user.extra_client_slots})")
        return {
            "status": "ok",
            "action": "addon_applied",
            "user_id": user_id,
            "slots_added": slots,
        }

    # Caminho SUBSCRIPTION — nova assinatura
    session_id = _get_attr(session_obj, "id")
    existing_sub = db.query(Subscription).filter(
        Subscription.stripe_checkout_session_id == session_id
    ).first()
    if existing_sub:
        return {
            "status": "already_processed",
            "reason": "checkout_session_id existe",
            "subscription_id": existing_sub.id,
        }

    # Normalizar plano (lazy import pra evitar circular)
    try:
        from app.api.auth import _normalize_plan
        plan = _normalize_plan(raw_plan)
    except Exception:
        plan = (raw_plan or "free").lower()

    stripe_sub_id = _get_attr(session_obj, "subscription")
    if stripe_sub_id and not isinstance(stripe_sub_id, str):
        stripe_sub_id = _get_attr(stripe_sub_id, "id")

    # Real Stripe period (com fallback)
    period_start, period_end, period_source = _resolve_subscription_period(stripe_sub_id)

    # Real amount (chain 3 niveis)
    amount = _resolve_amount(session_obj, stripe_sub_id, plan)
    currency = (_get_attr(session_obj, "currency") or "brl").lower()[:3]
    customer_id = _resolve_customer_id(session_obj)

    # Atualizar User
    user.plan = plan
    if customer_id:
        user.stripe_customer_id = customer_id
    try:
        user.plan_activated_at = datetime.now(timezone.utc)
    except Exception:
        pass

    # Criar Subscription
    sub = Subscription(
        user_id=user_id,
        stripe_subscription_id=stripe_sub_id,
        stripe_checkout_session_id=session_id,
        plan=plan,
        status="active",
        amount=amount,
        currency=currency,
        current_period_start=period_start,
        current_period_end=period_end,
        period_source=period_source,
    )
    db.add(sub)
    db.commit()
    logger.info(
        f"Subscription criada: user={user_id} plan={plan} amount={amount} "
        f"period_source={period_source}"
    )
    return {
        "status": "ok",
        "action": "subscription_created",
        "user_id": user_id,
        "plan": plan,
        "amount_brl": amount,
        "period_source": period_source,
    }


def _handle_invoice_paid(event: Any, db: Any) -> dict[str, Any]:
    """invoice.paid: renova periodo + persiste InvoicePayment (Tier 2.3.1)."""
    from database.models import Subscription

    invoice_obj = event.data.object if hasattr(event, "data") else event["data"]["object"]
    stripe_sub_id = _get_attr(invoice_obj, "subscription")
    if stripe_sub_id and not isinstance(stripe_sub_id, str):
        stripe_sub_id = _get_attr(stripe_sub_id, "id")

    if stripe_sub_id:
        sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()
        if sub:
            sub.status = "active"
            # Renovacao: atualizar period_end (idealmente da invoice.period_end)
            inv_period_end = _get_attr(invoice_obj, "period_end")
            if inv_period_end:
                try:
                    sub.current_period_end = datetime.fromtimestamp(int(inv_period_end), tz=timezone.utc)
                except (TypeError, ValueError):
                    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
            else:
                sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
            db.commit()

    # Tier 2.3.1: persistir InvoicePayment
    event_id = _get_attr(event, "id")
    try:
        from app.api._billing_helpers import persist_invoice_payment
        created, payment_id = persist_invoice_payment(
            db, invoice_obj, raw_event_id=event_id
        )
        return {
            "status": "ok",
            "action": "invoice_paid_processed",
            "invoice_payment_created": created,
            "invoice_payment_id": payment_id,
        }
    except Exception as e:
        logger.warning(f"persist_invoice_payment falhou: {e}")
        return {"status": "ok_partial", "error": str(e)[:200]}


def _handle_subscription_updated(event: Any, db: Any) -> dict[str, Any]:
    from database.models import Subscription

    sub_data = event.data.object if hasattr(event, "data") else event["data"]["object"]
    sub_id = _get_attr(sub_data, "id")
    if not sub_id:
        return {"status": "skipped", "reason": "no subscription id"}

    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == sub_id
    ).first()
    if not sub:
        return {"status": "skipped", "reason": f"subscription {sub_id} not in db"}

    new_status = _get_attr(sub_data, "status", "active") or "active"
    sub.status = new_status
    period_end_ts = _get_attr(sub_data, "current_period_end")
    if period_end_ts:
        try:
            sub.current_period_end = datetime.fromtimestamp(int(period_end_ts), tz=timezone.utc)
            sub.period_source = "stripe_api"  # Stripe enviou direto = autentico
        except (TypeError, ValueError):
            pass
    db.commit()
    return {"status": "ok", "action": "subscription_updated", "stripe_sub_id": sub_id, "new_status": new_status}


def _handle_subscription_deleted(event: Any, db: Any) -> dict[str, Any]:
    from database.models import Subscription, User

    sub_data = event.data.object if hasattr(event, "data") else event["data"]["object"]
    sub_id = _get_attr(sub_data, "id")
    if not sub_id:
        return {"status": "skipped", "reason": "no subscription id"}

    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == sub_id
    ).first()
    if not sub:
        return {"status": "skipped", "reason": f"subscription {sub_id} not in db"}

    sub.status = "cancelled"
    sub.cancelled_at = datetime.now(timezone.utc)
    user = db.query(User).filter(User.id == sub.user_id).first()
    if user:
        user.plan = "free"
    db.commit()
    return {"status": "ok", "action": "subscription_cancelled", "stripe_sub_id": sub_id}


def _handle_charge_refunded(event: Any, db: Any) -> dict[str, Any]:
    """charge.refunded: aplica refund cumulative em InvoicePayment (Tier 2.3.3).

    Sentry alert level=warning com fingerprint per-tenant (issue por user_id —
    permite detectar padrao 'user X com N refunds em periodo' sem ruido global).
    """
    from app.api._billing_helpers import apply_charge_refunded
    from database.models import InvoicePayment

    charge_obj = event.data.object if hasattr(event, "data") else event["data"]["object"]
    event_id = _get_attr(event, "id")

    action, payment_id, refunded_brl = apply_charge_refunded(
        db, charge_obj, raw_event_id=event_id
    )

    # Sentry alert apenas em refund efetivamente aplicado
    if action == "updated" and payment_id is not None:
        try:
            payment = db.query(InvoicePayment).filter(InvoicePayment.id == payment_id).first()
            if payment is not None:
                amount_paid_brl = (payment.amount_cents or 0) / 100.0
                refund_type = "full" if payment.status == "refunded" else "partial"
                user_id = payment.user_id or 0
                try:
                    import sentry_sdk
                    with sentry_sdk.new_scope() as scope:
                        # Per-tenant fingerprint: 1 issue por user, agrupa events do mesmo
                        scope.fingerprint = ["stripe-refund", str(user_id)]
                        scope.set_tag("refund", "true")
                        scope.set_tag("refund_type", refund_type)
                        scope.set_tag("user_id", str(user_id))
                        scope.set_extra("invoice_id", payment.stripe_invoice_id)
                        scope.set_extra("amount_refunded_brl", round(refunded_brl or 0.0, 2))
                        scope.set_extra("amount_paid_brl", round(amount_paid_brl, 2))
                        scope.set_extra("refund_count", payment.refund_count)
                        scope.set_extra("currency", payment.currency)
                        scope.set_user({"id": str(user_id)})
                        sentry_sdk.capture_message(
                            f"Refund processado ({refund_type}): "
                            f"R${refunded_brl:.2f} de R${amount_paid_brl:.2f} "
                            f"(invoice {payment.stripe_invoice_id})",
                            level="warning",
                        )
                except Exception:
                    pass
        except Exception:
            pass

    return {
        "status": "ok" if action == "updated" else "skipped",
        "action": action,
        "invoice_payment_id": payment_id,
        "refunded_brl": refunded_brl,
    }


def _handle_invoice_payment_failed(event: Any, db: Any) -> dict[str, Any]:
    from database.models import Subscription

    invoice_obj = event.data.object if hasattr(event, "data") else event["data"]["object"]
    stripe_sub_id = _get_attr(invoice_obj, "subscription")
    if stripe_sub_id and not isinstance(stripe_sub_id, str):
        stripe_sub_id = _get_attr(stripe_sub_id, "id")
    if not stripe_sub_id:
        return {"status": "skipped", "reason": "no subscription id"}

    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == stripe_sub_id
    ).first()
    if sub:
        sub.status = "past_due"
        db.commit()
    return {"status": "ok", "action": "marked_past_due", "stripe_sub_id": stripe_sub_id}


# ---------------------------------------------------------------------------
# DISPATCH PRINCIPAL — exportado pra ser chamado pelos 2 routes thin
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, Any] = {
    "checkout.session.completed": _handle_checkout_session_completed,
    "invoice.paid": _handle_invoice_paid,
    "invoice.payment_failed": _handle_invoice_payment_failed,
    "charge.refunded": _handle_charge_refunded,  # Tier 2.3.3
    "customer.subscription.updated": _handle_subscription_updated,
    "customer.subscription.deleted": _handle_subscription_deleted,
}


def dispatch_stripe_event(event: Any, db: Any, *, source_route: str) -> dict[str, Any]:
    """Single source of truth pra processamento de webhook Stripe.

    Args:
        event: stripe.Event (ou dict com mesma shape)
        db: SQLAlchemy Session ja aberta (caller fecha)
        source_route: rotulo "auth_v1" | "billing_v1" pra telemetria

    Returns:
        dict com status (ok | already_processed | skipped | error) +
        contexto pra response do route.

    NUNCA propaga excecao. Falha de processamento eh capturada via Sentry +
    registrada em WebhookHit.error, e route ainda retorna 200 (Stripe retry
    em 5xx pode causar duplicacao desnecessaria; nossa idempotency cuida).
    """
    from database.models import StripeEvent, WebhookHit

    event_id = _get_attr(event, "id")
    event_type = _get_attr(event, "type", "unknown") or "unknown"

    # 1. Registra hit ANTES de tudo (auditoria + telemetria)
    hit = WebhookHit(
        route=source_route,
        event_type=event_type,
        stripe_event_id=event_id,
        processed=True,  # vira False se idempotency skip
    )
    try:
        db.add(hit)
        db.commit()
        db.refresh(hit)
    except Exception as e:
        logger.warning(f"WebhookHit insert falhou: {e}")
        try:
            db.rollback()
        except Exception:
            pass

    try:
        # 2. Idempotency check via StripeEvent table (mesmo padrao do auth.py)
        if event_id:
            existing_evt = db.query(StripeEvent).filter(
                StripeEvent.stripe_event_id == event_id
            ).first()
            if existing_evt:
                logger.info(f"⚠️ Stripe event ja processado (idempotente): {event_id}")
                # Marca hit como nao-processado pra telemetria
                try:
                    hit.processed = False
                    db.commit()
                except Exception:
                    pass
                return {
                    "status": "already_processed",
                    "event_id": event_id,
                    "event_type": event_type,
                    "route": source_route,
                }
            # Registra evento como processado ANTES de chamar handler (defensivo
            # contra retry de Stripe se handler crashar mid-execucao)
            db.add(StripeEvent(stripe_event_id=event_id, event_type=event_type))
            db.commit()

        # 3. Dispatch
        handler = _HANDLERS.get(event_type)
        if handler is None:
            return {
                "status": "ignored",
                "event_type": event_type,
                "route": source_route,
                "reason": "no handler registered",
            }

        result = handler(event, db)
        result.setdefault("route", source_route)
        result.setdefault("event_id", event_id)
        result.setdefault("event_type", event_type)
        return result

    except Exception as e:
        logger.error(f"dispatch_stripe_event erro (event_id={event_id}): {e}", exc_info=True)
        # Sentry capture: falha em handler de webhook fiscal eh CRITICA
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        # Atualiza WebhookHit.error pra forensica
        try:
            hit.error = str(e)[:1000]
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        # NUNCA propaga — webhook deve retornar 200 mesmo em falha de handler
        # (Stripe retry agressivo + nossa idempotency = duplicacao indesejada)
        return {
            "status": "error",
            "error": str(e)[:200],
            "route": source_route,
            "event_id": event_id,
            "event_type": event_type,
        }
