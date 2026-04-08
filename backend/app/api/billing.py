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
    current_user: User = Depends(get_current_user)
):
    """Lista todas as faturas/contas do usuario autenticado."""
    invoices = (
        db.query(Invoice)
        .filter(Invoice.user_id == current_user.id)
        .order_by(Invoice.created_at.desc())
        .all()
    )
    return invoices


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna uma fatura especifica do usuario."""
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura nao encontrada")
    return invoice


@router.get("/subscription", response_model=Optional[SubscriptionOut])
def get_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna a assinatura ativa do usuario."""
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
            Subscription.status == "active"
        )
        .first()
    )
    return subscription


@router.post("/checkout")
def create_checkout_session(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cria sessao de checkout no Stripe e retorna URL de pagamento."""
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Pagamentos nao configurados")

    plan_key = payload.plan.lower()
    plan_info = PLANS.get(plan_key, {})

    logger.info(f"Checkout request: plan={plan_key}, user={current_user.email}")

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
                email=current_user.email,
                name=current_user.full_name or current_user.email,
                metadata={"user_id": str(current_user.id)},
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
            metadata={"user_id": str(current_user.id), "plan": payload.plan},
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
    current_user: User = Depends(get_current_user)
):
    """Cria sessao de checkout para addon +10 clientes/fornecedores (compra unica R$12,90)."""
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Pagamentos nao configurados")

    logger.info(f"Addon checkout request: user={current_user.email}")

    try:
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.full_name or current_user.email,
                metadata={"user_id": str(current_user.id)},
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
                "user_id": str(current_user.id),
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
    current_user: User = Depends(get_current_user)
):
    """Cancela a assinatura ativa do usuario (ao final do periodo)."""
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
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
    """Webhook Stripe - processa eventos de pagamento e assinatura."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not endpoint_secret:
        raise HTTPException(status_code=503, detail="Webhook secret nao configurado")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload invalido")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Assinatura invalida")

    event_type = event["type"]
    logger.info(f"Webhook received: {event_type}")

    if event_type == "checkout.session.completed":
        session_obj = event["data"]["object"]
        user_id = session_obj.get("metadata", {}).get("user_id")
        plan = session_obj.get("metadata", {}).get("plan", "")
        addon_type = session_obj.get("metadata", {}).get("addon_type", "")
        stripe_sub_id = session_obj.get("subscription")
        stripe_customer_id = session_obj.get("customer")

        if addon_type == "extra_clients" and user_id:
            extra_clients = int(session_obj.get("metadata", {}).get("extra_clients", "10"))
            extra_suppliers = int(session_obj.get("metadata", {}).get("extra_suppliers", "10"))
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                user.extra_client_slots = (user.extra_client_slots or 0) + extra_clients
                user.extra_supplier_slots = (user.extra_supplier_slots or 0) + extra_suppliers
                user.stripe_customer_id = stripe_customer_id
                db.commit()
                logger.info(f"Addon applied: user={user_id}, +{extra_clients} clients, +{extra_suppliers} suppliers")

        elif user_id and stripe_sub_id and plan:
            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
            sub = Subscription(
                user_id=int(user_id),
                stripe_subscription_id=stripe_sub_id,
                stripe_checkout_session_id=session_obj.get("id"),
                plan=plan,
                status="active",
                current_period_start=datetime.fromtimestamp(stripe_sub["current_period_start"], tz=timezone.utc),
                current_period_end=datetime.fromtimestamp(stripe_sub["current_period_end"], tz=timezone.utc),
                amount=(session_obj.get("amount_total") or 0) / 100,
                currency=(session_obj.get("currency") or "brl").upper(),
            )
            db.add(sub)
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                user.plan = plan
                user.stripe_customer_id = stripe_customer_id
                user.plan_activated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Subscription created: user={user_id}, plan={plan}")

    elif event_type == "customer.subscription.updated":
        stripe_sub = event["data"]["object"]
        sub = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_sub["id"])
            .first()
        )
        if sub:
            sub.status = stripe_sub["status"]
            sub.current_period_end = datetime.fromtimestamp(stripe_sub["current_period_end"], tz=timezone.utc)
            db.commit()

    elif event_type == "customer.subscription.deleted":
        stripe_sub = event["data"]["object"]
        sub = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_sub["id"])
            .first()
        )
        if sub:
            sub.status = "cancelled"
            db.commit()
            user = db.query(User).filter(User.id == sub.user_id).first()
            if user:
                user.plan = "free"
                db.commit()

    elif event_type == "invoice.payment_failed":
        stripe_invoice = event["data"]["object"]
        stripe_sub_id = stripe_invoice.get("subscription")
        if stripe_sub_id:
            sub = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == stripe_sub_id)
                .first()
            )
            if sub:
                sub.status = "past_due"
                db.commit()

    return {"received": True, "type": event_type}
