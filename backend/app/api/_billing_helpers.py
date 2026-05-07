"""
_billing_helpers — funcoes compartilhadas entre webhook handlers Stripe.

Este modulo existe pra evitar duplicacao do codigo que persiste pagamentos
em InvoicePayment, dado que ha 2 webhook handlers paralelos (auth.py +
billing.py). Idempotente: re-chamada com mesmo stripe_invoice_id = no-op.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _stripe_ts_to_dt(ts: Optional[int]) -> Optional[datetime]:
    """Converte timestamp Unix do Stripe pra datetime UTC. None se invalido."""
    if ts is None or ts == 0:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _resolve_paid_at(invoice_obj: Any) -> datetime:
    """Resolve timestamp 'pago em' com fallback chain.

    Ordem (Stripe pode nao popular todos):
      1. status_transitions.paid_at  (canonico do Stripe)
      2. created                      (fallback)
      3. utcnow()                     (defensivo, raro)
    """
    transitions = getattr(invoice_obj, "status_transitions", None) or {}
    if hasattr(transitions, "get"):
        paid_at_ts = transitions.get("paid_at")
    else:
        paid_at_ts = getattr(transitions, "paid_at", None)
    dt = _stripe_ts_to_dt(paid_at_ts)
    if dt is not None:
        return dt
    dt = _stripe_ts_to_dt(getattr(invoice_obj, "created", None))
    if dt is not None:
        return dt
    return datetime.now(timezone.utc)


def _resolve_user_id_from_subscription(db, stripe_subscription_id: Optional[str]) -> Optional[int]:
    """Resolve user_id a partir de stripe_subscription_id via Subscription table."""
    if not stripe_subscription_id:
        return None
    try:
        from database.models import Subscription
        sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_subscription_id
        ).first()
        return sub.user_id if sub else None
    except Exception:
        return None


def persist_invoice_payment(
    db,
    invoice_obj: Any,
    *,
    raw_event_id: Optional[str] = None,
    capture_sentry_on_error: bool = True,
) -> tuple[bool, Optional[int]]:
    """Persiste InvoicePayment de um Stripe Invoice object. Idempotente.

    Args:
        db: Session SQLAlchemy ativa.
        invoice_obj: objeto Stripe Invoice (do webhook event.data.object).
        raw_event_id: stripe_event_id do StripeEvent que originou (auditoria).
        capture_sentry_on_error: se True, captura excecoes via Sentry alem do log.

    Returns:
        (created, payment_id):
            created=True se inseriu nova linha; False se ja existia ou falhou.
            payment_id=id da linha (ou None se falhou).

    NUNCA propaga excecao — falha aqui nao pode bloquear o fluxo do webhook.
    Sentry capture na falha por causa de criticidade fiscal:
      'webhook 200 + dado financeiro evapora silenciosamente' eh o pior bug.
    """
    try:
        from database.models import InvoicePayment

        invoice_id = getattr(invoice_obj, "id", None)
        if not invoice_id:
            logger.warning("persist_invoice_payment: invoice_obj sem .id, skip")
            return False, None

        # 1. Idempotency check — caminho primario (evita rollback custoso)
        existing = db.query(InvoicePayment).filter(
            InvoicePayment.stripe_invoice_id == invoice_id
        ).first()
        if existing:
            logger.debug(f"InvoicePayment ja existe pra invoice_id={invoice_id}")
            return False, existing.id

        # 2. Extrair campos com defaults defensivos
        amount_cents = int(getattr(invoice_obj, "amount_paid", 0) or 0)
        currency = (getattr(invoice_obj, "currency", "brl") or "brl").lower()[:3]
        status = (getattr(invoice_obj, "status", "paid") or "paid").lower()[:20]
        # Se Stripe ja enviou um status diferente de "paid" (ex: "open"), nao registra
        # — esperamos o evento "invoice.paid" que so dispara em transicao paid.
        # Aqui force "paid" pq o handler so chama isso em invoice.paid.
        status = "paid"

        paid_at = _resolve_paid_at(invoice_obj)
        period_start = _stripe_ts_to_dt(getattr(invoice_obj, "period_start", None))
        period_end = _stripe_ts_to_dt(getattr(invoice_obj, "period_end", None))

        stripe_subscription_id = getattr(invoice_obj, "subscription", None)
        if stripe_subscription_id and not isinstance(stripe_subscription_id, str):
            # Pode vir como objeto expandido — extrai .id
            stripe_subscription_id = getattr(stripe_subscription_id, "id", None)

        stripe_customer_id = getattr(invoice_obj, "customer", None)
        if stripe_customer_id and not isinstance(stripe_customer_id, str):
            stripe_customer_id = getattr(stripe_customer_id, "id", None)

        user_id = _resolve_user_id_from_subscription(db, stripe_subscription_id)

        # 3. Insert (unique constraint stripe_invoice_id eh defesa em profundidade)
        payment = InvoicePayment(
            user_id=user_id,
            stripe_invoice_id=invoice_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            amount_cents=amount_cents,
            currency=currency,
            status=status,
            paid_at=paid_at,
            period_start=period_start,
            period_end=period_end,
            raw_event_id=raw_event_id,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        logger.info(
            f"InvoicePayment criado: invoice={invoice_id} "
            f"amount={amount_cents}c{currency} user={user_id} sub={stripe_subscription_id}"
        )
        return True, payment.id

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(
            f"InvoicePayment persistence FALHOU pra invoice_id="
            f"{getattr(invoice_obj, 'id', '?')}: {e}",
            exc_info=True,
        )
        if capture_sentry_on_error:
            # Falha silenciosa de fiscal data eh o pior bug — Sentry tem que gritar
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(e)
            except Exception:
                pass
        return False, None


def apply_charge_refunded(
    db,
    charge_obj: Any,
    *,
    raw_event_id: Optional[str] = None,
    capture_sentry_on_error: bool = True,
) -> tuple[str, Optional[int], Optional[float]]:
    """Aplica refund cumulative em InvoicePayment a partir de charge.refunded event.

    Stripe envia amount_refunded cumulativo (nao delta). Re-receber mesmo valor
    = idempotent no-op. Charge sem invoice (PaymentIntent direto sem subscription)
    = skip gracefully.

    Status transition baseado em cumulative:
      refund_amount == 0       -> "paid" (nunca acontece aqui mas defensivo)
      0 < refund < amount      -> "partial_refunded"
      refund >= amount         -> "refunded"

    Returns:
        (action, payment_id, refunded_brl):
            action: "skipped_no_invoice" | "skipped_invoice_not_found"
                  | "skipped_idempotent" | "updated"
            payment_id: id da InvoicePayment se atualizada (None caso contrario)
            refunded_brl: total cumulativo BRL apos update (None se skipped)

    NUNCA propaga excecao. Sentry capture em falha por criticidade fiscal.
    """
    try:
        from database.models import InvoicePayment, INVOICE_PAYMENT_STATUSES
        from datetime import datetime, timezone

        invoice_id = _get_str_attr(charge_obj, "invoice")
        if not invoice_id:
            logger.info(
                f"charge.refunded sem invoice (PaymentIntent direto): "
                f"charge_id={getattr(charge_obj, 'id', '?')} — skip"
            )
            return "skipped_no_invoice", None, None

        payment = db.query(InvoicePayment).filter(
            InvoicePayment.stripe_invoice_id == invoice_id
        ).first()
        if not payment:
            logger.warning(
                f"charge.refunded apontando pra invoice nao registrada: {invoice_id} — "
                f"InvoicePayment ausente. Use /admin/billing/resync-invoices."
            )
            return "skipped_invoice_not_found", None, None

        # Cumulative idempotency check ANTES de tocar o DB
        new_cumulative = int(getattr(charge_obj, "amount_refunded", 0) or 0)
        if payment.refund_amount_cents == new_cumulative and new_cumulative > 0:
            logger.debug(
                f"charge.refunded idempotente (cumulative inalterado): "
                f"invoice={invoice_id} refund={new_cumulative}c"
            )
            return "skipped_idempotent", payment.id, None

        # Transicao de status pelo cumulative
        if new_cumulative == 0:
            new_status = "paid"
        elif new_cumulative >= payment.amount_cents:
            new_status = "refunded"
        else:
            new_status = "partial_refunded"

        # Defesa em codigo: assert status no enum permitido (constante validada)
        if new_status not in INVOICE_PAYMENT_STATUSES:
            logger.error(f"status invalido derivado: {new_status!r} — abortando")
            return "skipped_invoice_not_found", None, None

        payment.refund_amount_cents = new_cumulative
        payment.refund_count = (payment.refund_count or 0) + 1
        payment.refunded_at = datetime.now(timezone.utc)
        payment.status = new_status
        db.commit()
        db.refresh(payment)

        refunded_brl = cents_to_brl(new_cumulative, payment.currency or "brl")
        logger.info(
            f"InvoicePayment refund aplicado: invoice={invoice_id} "
            f"refund={new_cumulative}c status={new_status} count={payment.refund_count}"
        )
        return "updated", payment.id, refunded_brl

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(
            f"apply_charge_refunded FALHOU pra charge="
            f"{getattr(charge_obj, 'id', '?')}: {e}",
            exc_info=True,
        )
        if capture_sentry_on_error:
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(e)
            except Exception:
                pass
        return "skipped_invoice_not_found", None, None


def _get_str_attr(obj: Any, key: str) -> Optional[str]:
    """Extrai atributo como string. Stripe campos podem vir como obj expandido."""
    val = getattr(obj, key, None)
    if val is None and isinstance(obj, dict):
        val = obj.get(key)
    if val is None:
        return None
    if isinstance(val, str):
        return val
    # Objeto expandido — pega .id
    return getattr(val, "id", None) or (val.get("id") if isinstance(val, dict) else None)


def cents_to_brl(amount_cents: int, currency: str, usd_brl_rate: float = 5.20) -> float:
    """Converte amount_cents pra valor BRL.

    BRL: amount_cents/100 (direto)
    USD: amount_cents/100 * usd_brl_rate
    Outras: assume BRL e loga warning (raro mas defensivo)
    """
    base = (amount_cents or 0) / 100.0
    if not currency:
        return base
    c = currency.lower()
    if c == "brl":
        return base
    if c == "usd":
        return base * float(usd_brl_rate)
    logger.warning(f"cents_to_brl: currency desconhecida '{currency}', assumindo BRL")
    return base
