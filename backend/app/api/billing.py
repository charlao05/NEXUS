from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database.models import get_db, Invoice, Subscription, User  # type: ignore[import]
from app.api.auth import get_current_user  # type: ignore[import]
from app.schemas.billing import InvoiceOut, SubscriptionOut, SubscriptionCreate  # type: ignore[import]
from typing import List, Optional
import stripe
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["billing"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

# PLANOS: preco configurado via env vars (price_id do Stripe Dashboard)
PLANS = {
    "essencial": {
        "stripe_price_id": os.getenv("STRIPE_PRICE_ESSENCIAL", ""),
        "name": "Essencial",
        "amount": 2990,
        "currency": "brl",
    },
    "profissional": {
        "stripe_price_id": os.getenv("STRIPE_PRICE_PROFISSIONAL", ""),
        "name": "Profissional",
        "amount": 5990,
        "currency": "brl",
    },
    "completo": {
        "stripe_price_id": os.getenv("STRIPE_PRICE_COMPLETO", ""),
        "name": "Completo",
        "amount": 8990,
        "currency": "brl",
    },
}


@router.get("/invoices", response_model=List[InvoiceOut])
def list_invoices(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Lista todas as faturas/contas do usuario autenticado."""
    invoices = (
        db.query(Invoice)
        .filter(Invoice.user_id == current_user["user_id"])
        .order_by(Invoice.created_at.desc())
        .all()
    )
    return invoices


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Retorna uma fatura especifica do usuario."""
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.user_id == current_user["user_id"])
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura nao encontrada")
    return invoice


@router.get("/subscription", response_model=Optional[SubscriptionOut])
def get_subscription(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Retorna a assinatura ativa do usuario."""
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user["user_id"],
            Subscription.status == "active"
        )
        .first()
    )
    return subscription


@router.post("/checkout")
def create_checkout_session(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Cria sessao de checkout no Stripe e retorna URL de pagamento.

    ☠️ ESTA ROTA NUNCA EXECUTA — E-040.

    `auth.py:443` e `billing.py:14` declaram o MESMO prefixo /api/auth, e ambos
    definem POST /checkout. `main.py:228` monta `auth` primeiro, e o FastAPI
    resolve sempre para o primeiro registrado. Quem atende o checkout de
    verdade e `auth.py:1166`.

    ⚠️ E o corpo abaixo esta QUEBRADO: usa `current_user.stripe_customer_id`,
    mas `get_current_user` devolve um DICT (auth.py:341). Corrigi as 4 rotas
    VIVAS deste arquivo em 01/08/2026 (E-043) e deixei estas duas como estao,
    de proposito: meio-consertar codigo morto esconde que ele e morto.

    ANTES DE DESSOMBREAR ESTA ROTA: decida qual das duas implementacoes de
    checkout sobrevive (elas nao sao identicas) e conserte o dict aqui.
    """
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Pagamentos nao configurados")

    plan_key = payload.plan.lower()
    plan_info = PLANS.get(plan_key, {})

    logger.info(f"Checkout request: plan={plan_key}, user={current_user.get("email")}")

    resolved_price_id = (
        getattr(payload, 'price_id', None)
        or plan_info.get("stripe_price_id", "")
    )

    if resolved_price_id:
        line_items = [{"price": resolved_price_id, "quantity": 1}]
        logger.info(f"Using price_id: {resolved_price_id[:20]}...")
    else:
        amount = plan_info.get("amount", 2990)
        currency = plan_info.get("currency", "brl")
        name = plan_info.get("name", payload.plan.capitalize())
        line_items = [{
            "price_data": {
                "currency": currency,
                "unit_amount": amount,
                "recurring": {"interval": "month"},
                "product_data": {"name": f"NEXUS {name}"},
            },
            "quantity": 1,
        }]
        logger.info(f"Using price_data fallback: {name} {amount} {currency}")

    try:
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.get("email"),
                name=current_user.get("full_name") or current_user.get("email"),
                metadata={"user_id": str(current_user["user_id"])},
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
            logger.info(f"Stripe customer created: {customer.id}")

        frontend_url = os.getenv("FRONTEND_URL", "https://app.nexxusapp.com.br")
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=line_items,
            mode="subscription",
            allow_promotion_codes=True,
            success_url=f"{frontend_url}/dashboard?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}/planos?checkout=cancelled",
            metadata={"user_id": str(current_user["user_id"]), "plan": payload.plan},
        )
        logger.info(f"Checkout session created: {session.id}")
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe checkout error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected checkout error: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar checkout")


@router.post("/checkout/addon-clients")
def create_addon_checkout(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Cria sessao de checkout para addon +10 clientes/fornecedores (R$12,90).

    ☠️ ESTA ROTA TAMBEM NUNCA EXECUTA — mesma colisao de prefixo (E-040).
    Quem atende e `auth.py:1411`. E o corpo abaixo tem o mesmo defeito de dict
    da irma acima. Ver o docstring de `create_checkout_session`.
    """
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Pagamentos nao configurados")

    logger.info(f"Addon checkout request: user={current_user.get("email")}")

    try:
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.get("email"),
                name=current_user.get("full_name") or current_user.get("email"),
                metadata={"user_id": str(current_user["user_id"])},
            )
            current_user.stripe_customer_id = customer.id
            db.commit()

        frontend_url = os.getenv("FRONTEND_URL", "https://app.nexxusapp.com.br")
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "brl",
                    "unit_amount": 1290,
                    "product_data": {
                        "name": "NEXUS +10 Clientes/Fornecedores",
                        "description": "Adicione 10 clientes e 10 fornecedores extras ao seu plano atual",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{frontend_url}/dashboard?addon=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}/planos?addon=cancelled",
            metadata={
                "user_id": str(current_user["user_id"]),
                "addon_type": "extra_clients",
                "extra_clients": "10",
                "extra_suppliers": "10",
            },
        )
        logger.info(f"Addon checkout session created: {session.id}")
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe addon checkout error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected addon checkout error: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar checkout do addon")


@router.delete("/subscription")
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Cancela a assinatura ativa do usuario (ao final do periodo)."""
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user["user_id"],
            Subscription.status == "active"
        )
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Nenhuma assinatura ativa encontrada")
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Pagamentos nao configurados")
    try:
        if subscription.stripe_subscription_id:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
        subscription.status = "cancelled"
        db.commit()
        return {"message": "Assinatura sera cancelada ao final do periodo vigente"}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Webhook Stripe — route thin que delega pra dispatch_stripe_event.

    Tier 2.3.1.1: logica fundida vive em _stripe_webhook_handler.py.
    source_route="billing_v1" registrado em WebhookHit pra telemetria —
    permite descobrir empiricamente qual rota Stripe Dashboard esta usando
    de fato (auth_v1 vs billing_v1) antes de deprecar a inativa.
    """
    from app.api._stripe_webhook_handler import (
        validate_and_parse_webhook,
        dispatch_stripe_event,
    )
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = validate_and_parse_webhook(payload, sig_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload invalido")
    except Exception as e:
        if "signature" in str(type(e)).lower() or "SignatureVerification" in str(type(e)):
            raise HTTPException(status_code=400, detail="Assinatura invalida")
        raise

    # Mesma correção de auth.py:1537 (E-042). Ver o comentário longo lá.
    # Webhook não tem usuário autenticado; o dono do evento é resolvido pelo
    # handler a partir do customer/metadata.
    from app.core.tenant import sem_tenant

    with sem_tenant("webhook Stripe (billing_v1): evento de sistema, sem "
                    "usuário autenticado — o dono é resolvido pelo handler"):
        return dispatch_stripe_event(event, db, source_route="billing_v1")
