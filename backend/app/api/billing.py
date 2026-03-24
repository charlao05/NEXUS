from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database.models import get_db, Invoice, Subscription, User  # type: ignore[import]
from app.api.auth import get_current_user  # type: ignore[import]
from app.schemas.billing import InvoiceOut, SubscriptionOut, SubscriptionCreate  # type: ignore[import]
from typing import List, Optional
import stripe
import os
from datetime import datetime

router = APIRouter(prefix="/billing", tags=["billing"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

# PLANOS: preco configurado via env vars (price_id do Stripe Dashboard)
PLANS = {
    "essencial": {
        "stripe_price_id": os.getenv("STRIPE_PRICE_ESSENCIAL", ""),
        "name": "Essencial",
        "amount": 4700,
        "currency": "brl",
    },
    "profissional": {
        "stripe_price_id": os.getenv("STRIPE_PRICE_PROFISSIONAL", ""),
        "name": "Profissional",
        "amount": 9700,
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

    # Determina line_item: usa price_id do payload, depois do PLANS, senao fallback price_data
    plan_key = payload.plan.lower()
    plan_info = PLANS.get(plan_key, {})

    # Prioridade: 1) price_id enviado pelo frontend, 2) price_id do PLANS, 3) price_data (fallback)
    resolved_price_id = (
        payload.price_id
        or plan_info.get("stripe_price_id", "")
    )

    if resolved_price_id:
        line_items = [{"price": resolved_price_id, "quantity": 1}]
    else:
        # Fallback: usa price_data inline para nao bloquear checkout
        amount = plan_info.get("amount", 4700)
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

    try:
        # Cria ou recupera customer no Stripe
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.full_name or current_user.email,
                metadata={"user_id": str(current_user.id)},
            )
            current_user.stripe_customer_id = customer.id
            db.commit()

        frontend_url = os.getenv("FRONTEND_URL", "https://nexxusapp.com.br")
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=line_items,
            mode="subscription",
            success_url=f"{frontend_url}/dashboard?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}/planos?checkout=cancelled",
            metadata={"user_id": str(current_user.id), "plan": payload.plan},
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    """Webhook Stripe — processa eventos de pagamento e assinatura."""
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

    if event_type == "checkout.session.completed":
        # Checkout concluido — criar/atualizar assinatura
        session_obj = event["data"]["object"]
        user_id = session_obj.get("metadata", {}).get("user_id")
        plan = session_obj.get("metadata", {}).get("plan", "essencial")
        stripe_sub_id = session_obj.get("subscription")
        stripe_customer_id = session_obj.get("customer")

        if user_id and stripe_sub_id:
            # Buscar dados da assinatura no Stripe
            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
            sub = Subscription(
                user_id=int(user_id),
                stripe_subscription_id=stripe_sub_id,
                stripe_checkout_session_id=session_obj.get("id"),
                plan=plan,
                status="active",
                current_period_start=datetime.utcfromtimestamp(stripe_sub["current_period_start"]),
                current_period_end=datetime.utcfromtimestamp(stripe_sub["current_period_end"]),
                amount=(session_obj.get("amount_total") or 0) / 100,
                currency=(session_obj.get("currency") or "brl").upper(),
            )
            db.add(sub)
            # Atualizar plano do usuario
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                user.plan = plan
                user.stripe_customer_id = stripe_customer_id
                user.plan_activated_at = datetime.utcnow()
            db.commit()

    elif event_type == "customer.subscription.updated":
        stripe_sub = event["data"]["object"]
        sub = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_sub["id"])
            .first()
        )
        if sub:
            sub.status = stripe_sub["status"]
            sub.current_period_end = datetime.utcfromtimestamp(stripe_sub["current_period_end"])
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
            # Rebaixar usuario para free
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
