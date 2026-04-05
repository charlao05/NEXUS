"""
NEXUS — Billing API (consulta)
===============================
Endpoints READ-ONLY de billing.
Checkout, webhook e processamento de pagamentos ficam em auth.py
(endpoint único, com idempotência e validação de assinatura).

Endpoints:
  GET /billing/invoices           — lista faturas do usuário
  GET /billing/invoices/{id}      — detalhe de uma fatura
  GET /billing/subscription       — assinatura ativa
  DELETE /billing/subscription    — cancela assinatura ao final do período
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.models import get_db, Invoice, Subscription, User  # type: ignore[import]
from app.api.auth import get_current_user  # type: ignore[import]
from app.schemas.billing import InvoiceOut, SubscriptionOut  # type: ignore[import]
from typing import List, Optional
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# INVOICES (faturas)
# ---------------------------------------------------------------------------

@router.get("/invoices", response_model=List[InvoiceOut])
def list_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista todas as faturas do usuário autenticado."""
    return (
        db.query(Invoice)
        .filter(Invoice.user_id == current_user.id)
        .order_by(Invoice.created_at.desc())
        .all()
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna uma fatura específica do usuário."""
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")
    return invoice


# ---------------------------------------------------------------------------
# SUBSCRIPTION (assinatura)
# ---------------------------------------------------------------------------

@router.get("/subscription", response_model=Optional[SubscriptionOut])
def get_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna a assinatura ativa do usuário."""
    return (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
            Subscription.status == "active",
        )
        .first()
    )


@router.delete("/subscription")
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancela a assinatura ativa (ao final do período vigente)."""
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
            Subscription.status == "active",
        )
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Nenhuma assinatura ativa")

    # Cancelar no Stripe
    if subscription.stripe_subscription_id:
        try:
            import stripe
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
            if stripe.api_key:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True,
                )
        except Exception as e:
            logger.error(f"Erro ao cancelar no Stripe: {e}")
            raise HTTPException(status_code=500, detail="Erro ao processar cancelamento")

    subscription.status = "cancelled"  # type: ignore[assignment]
    db.commit()
    return {"message": "Assinatura será cancelada ao final do período vigente"}
