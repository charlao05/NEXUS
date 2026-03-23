from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class InvoiceOut(BaseModel):
    """Schema de saida para faturas/contas a receber."""
    id: int
    user_id: Optional[int] = None
    client_id: Optional[int] = None
    description: str
    amount: float
    due_date: Optional[str] = None
    paid_at: Optional[datetime] = None
    status: str
    reminders_sent: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubscriptionOut(BaseModel):
    """Schema de saida para assinaturas Stripe."""
    id: int
    user_id: int
    stripe_subscription_id: Optional[str] = None
    stripe_checkout_session_id: Optional[str] = None
    plan: str
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    amount: float = 0.0
    currency: str = "brl"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubscriptionCreate(BaseModel):
    """Schema de entrada para criar assinatura via Stripe."""
    price_id: str
    plan: str


class CheckoutSessionOut(BaseModel):
    """Retorno da criacao de sessao de checkout Stripe."""
    checkout_url: str
    session_id: str
