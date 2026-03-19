from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.billing import Invoice, Subscription
from app.schemas.billing import InvoiceOut, SubscriptionOut, SubscriptionCreate
from typing import List
import stripe
import os
from datetime import datetime

router = APIRouter(prefix="/billing", tags=["billing"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


@router.get("/invoices", response_model=List[InvoiceOut])
def list_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista todas as faturas do usuario autenticado."""
    invoices = db.query(Invoice).filter(Invoice.user_id == current_user.id).order_by(Invoice.created_at.desc()).all()
    return invoices


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna uma fatura especifica."""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == current_user.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura nao encontrada")
    return invoice


@router.get("/subscription", response_model=SubscriptionOut)
def get_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna a assinatura ativa do usuario."""
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.status == "active"
    ).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Nenhuma assinatura ativa encontrada")
    return subscription


@router.post("/subscription", response_model=SubscriptionOut)
def create_subscription(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cria uma nova assinatura via Stripe."""
    try:
        # Cria ou recupera o customer no Stripe
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.full_name or current_user.email,
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        else:
            customer = stripe.Customer.retrieve(current_user.stripe_customer_id)

        # Cria a assinatura no Stripe
        stripe_subscription = stripe.Subscription.create(
            customer=current_user.stripe_customer_id,
            items=[{"price": payload.price_id}],
            expand=["latest_invoice.payment_intent"],
        )

        # Salva no banco
        subscription = Subscription(
            user_id=current_user.id,
            stripe_subscription_id=stripe_subscription.id,
            stripe_customer_id=current_user.stripe_customer_id,
            plan=payload.plan,
            status=stripe_subscription.status,
            current_period_start=datetime.utcfromtimestamp(stripe_subscription.current_period_start),
            current_period_end=datetime.utcfromtimestamp(stripe_subscription.current_period_end),
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        return subscription

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e.user_message))


@router.delete("/subscription")
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancela a assinatura ativa do usuario."""
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.status == "active"
    ).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Nenhuma assinatura ativa encontrada")

    try:
        stripe.Subscription.delete(subscription.stripe_subscription_id)
        subscription.status = "canceled"
        db.commit()
        return {"message": "Assinatura cancelada com sucesso"}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e.user_message))


@router.post("/webhook")
async def stripe_webhook(request, db: Session = Depends(get_db)):
    """Recebe webhooks do Stripe para atualizar status de pagamento."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Trata eventos relevantes
    if event["type"] == "invoice.payment_succeeded":
        stripe_invoice = event["data"]["object"]
        invoice = Invoice(
            user_id=None,  # mapear pelo customer_id
            stripe_invoice_id=stripe_invoice["id"],
            amount=stripe_invoice["amount_paid"] / 100,
            currency=stripe_invoice["currency"].upper(),
            status="paid",
            paid_at=datetime.utcnow(),
        )
        db.add(invoice)
        db.commit()

    elif event["type"] == "customer.subscription.updated":
        stripe_sub = event["data"]["object"]
        sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub["id"]
        ).first()
        if sub:
            sub.status = stripe_sub["status"]
            db.commit()

    return {"received": True}
