"""
FastAPI Stripe Payment Integration
Endpoints para processar pagamentos com Stripe usando Payment Intents
"""

import os
import logging
from typing import Optional
from decimal import Decimal

import stripe
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Stripe with API key from environment
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if not STRIPE_SECRET_KEY:
    logger.warning("⚠️ STRIPE_SECRET_KEY not found in environment")
else:
    stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/payments", tags=["payments"])


# ==================== MODELS ====================

class CreatePaymentIntentRequest(BaseModel):
    """Request to create a Payment Intent"""
    amount: int = Field(..., gt=0, description="Amount in cents (e.g., 5000 = $50.00)")
    currency: str = Field(default="usd", description="Currency code (e.g., usd, brl)")
    description: str = Field(default="Payment", description="Payment description")
    email: Optional[str] = Field(None, description="Customer email")
    metadata: Optional[dict] = Field(None, description="Additional metadata")


class ConfirmPaymentIntentRequest(BaseModel):
    """Request to confirm a Payment Intent"""
    payment_intent_id: str = Field(..., description="Payment Intent ID")
    payment_method_id: str = Field(..., description="Payment Method ID")


class PaymentResponse(BaseModel):
    """Response after payment processing"""
    success: bool
    payment_intent_id: Optional[str] = None
    client_secret: Optional[str] = None
    amount: Optional[int] = None
    status: Optional[str] = None
    error: Optional[str] = None


# ==================== ENDPOINTS ====================

@router.post("/create-intent", response_model=PaymentResponse)
async def create_payment_intent(request: CreatePaymentIntentRequest):
    """
    Create a Stripe Payment Intent
    
    This endpoint creates a Payment Intent that the frontend can use
    to confirm payment securely.
    
    Args:
        request: Payment request details
        
    Returns:
        PaymentResponse with client_secret and payment_intent_id
    """
    try:
        # Validate amount (minimum $0.50)
        if request.amount < 50:
            raise ValueError("Minimum amount is $0.50 (50 cents)")
        
        logger.info(f"Creating Payment Intent: ${request.amount/100:.2f} {request.currency.upper()}")
        
        # Create Payment Intent
        payment_params = {
            "amount": request.amount,
            "currency": request.currency,
            "description": request.description,
            "metadata": request.metadata or {"service": "NEXUS"},
            "automatic_payment_methods": {"enabled": True},
        }
        
        # Only add receipt_email if provided
        if request.email:
            payment_params["receipt_email"] = request.email
        
        intent = stripe.PaymentIntent.create(**payment_params)
        
        logger.info(f"Payment Intent created: {intent.id}")
        
        return PaymentResponse(
            success=True,
            payment_intent_id=intent.id,
            client_secret=intent.client_secret,
            amount=intent.amount,
            status=intent.status,
        )
        
    except stripe.CardError as e:
        logger.error(f"Card error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Card error: {str(e)}"
        )
        
    except stripe.RateLimitError as e:
        logger.error("Rate limit exceeded")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later."
        )
        
    except stripe.InvalidRequestError as e:
        logger.error(f"Invalid request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
        
    except stripe.AuthenticationError as e:
        logger.error("Authentication error with Stripe")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication error with payment provider"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.post("/confirm-intent", response_model=PaymentResponse)
async def confirm_payment_intent(request: ConfirmPaymentIntentRequest):
    """
    Confirm a Stripe Payment Intent
    
    This endpoint is called after frontend confirms payment
    
    Args:
        request: Confirmation details
        
    Returns:
        PaymentResponse with success status
    """
    try:
        logger.info(f"Confirming Payment Intent: {request.payment_intent_id}")
        
        intent = stripe.PaymentIntent.confirm(
            request.payment_intent_id,
            payment_method=request.payment_method_id,
        )
        
        if intent.status in ["succeeded", "processing"]:
            logger.info(f"Payment succeeded: {intent.id}")
            return PaymentResponse(
                success=True,
                payment_intent_id=intent.id,
                amount=intent.amount,
                status=intent.status,
            )
        else:
            logger.warning(f"Payment not succeeded: {intent.status}")
            return PaymentResponse(
                success=False,
                status=intent.status,
                error=f"Payment status: {intent.status}",
            )
            
    except stripe.CardError as e:
        logger.error(f"Card error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Card declined: {str(e)}"
        )
        
    except Exception as e:
        logger.error(f"Error confirming intent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing payment"
        )


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhooks
    
    This endpoint receives events from Stripe
    (payment_intent.succeeded, payment_intent.failed, etc.)
    """
    payload = await request.body()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    if not webhook_secret:
        logger.warning("Webhook secret not configured")
        return {"status": "ok"}
    
    try:
        sig_header = request.headers.get("stripe-signature")
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle webhook events
    event_type = event["type"]
    
    if event_type == "payment_intent.succeeded":
        intent = event["data"]["object"]
        logger.info(f"✅ Payment succeeded: {intent['id']}")
        # TODO: Update database with payment success
        
    elif event_type == "payment_intent.payment_failed":
        intent = event["data"]["object"]
        logger.error(f"❌ Payment failed: {intent['id']}")
        # TODO: Handle payment failure
        
    elif event_type == "charge.refunded":
        charge = event["data"]["object"]
        logger.info(f"💰 Refund processed: {charge['id']}")
        # TODO: Handle refund
    
    return {"status": "received"}


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "stripe": "configured" if STRIPE_SECRET_KEY else "not_configured"
    }
