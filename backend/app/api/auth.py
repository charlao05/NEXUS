"""
NEXUS - Sistema de Autenticação e Pagamento (PRODUÇÃO)
======================================================
Autenticação REAL com banco de dados SQLAlchemy.
- Signup → salva User com bcrypt hash no SQLite
- Login → valida credenciais no banco
- JWT → tokens com expiração
- Stripe → checkout + webhook completo
- OAuth → Google/Facebook com persistência
"""

from fastapi import APIRouter, HTTPException, Depends, status, Header, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Any
from urllib.parse import quote
import os
import logging
import requests as http_requests
import jwt  # type: ignore[import-untyped]
import bcrypt  # type: ignore[import-untyped]
from secrets import token_urlsafe
from sqlalchemy.orm import Session

# Imports do banco de dados
from database.models import User, Subscription, Client, Invoice, SessionLocal  # type: ignore[import]

logger = logging.getLogger(__name__)


# ============================================================================
# SCHEMAS Pydantic
# ============================================================================

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    communication_preference: str = "email"  # email, whatsapp, sms


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: str
    plan: str
    refresh_token: Optional[str] = None


class UserProfile(BaseModel):
    user_id: str
    email: str
    full_name: str
    plan: str
    role: str = "user"
    communication_preference: str = "email"
    created_at: datetime
    subscription_expires: Optional[datetime] = None
    requests_used: int
    requests_limit: int


class PaymentCheckout(BaseModel):
    plan: str
    email: str


class SubscriptionResponse(BaseModel):
    status: str
    checkout_url: str
    session_id: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyPaymentRequest(BaseModel):
    session_id: str


# ============================================================================
# SEGURANÇA — Funções auxiliares
# ============================================================================

def hash_password(password: str) -> str:
    """Hash bcrypt seguro (12 rounds)"""
    salt = bcrypt.gensalt(rounds=12)  # type: ignore[no-untyped-call]
    return bcrypt.hashpw(password.encode(), salt).decode()  # type: ignore[no-untyped-call]


def verify_password(password: str, hash_pwd: str) -> bool:
    """Verifica senha em tempo constante"""
    try:
        return bcrypt.checkpw(password.encode(), hash_pwd.encode())  # type: ignore[no-untyped-call]
    except Exception:
        return False


# Mapeamento de nomes de plano antigos → canônicos
_PLAN_ALIASES = {"pro": "essencial", "enterprise": "completo"}


def _normalize_plan(raw: str | None) -> str:
    """Normaliza nome de plano: aliases antigos → canônicos."""
    p = str(raw or "free").strip().lower()
    return _PLAN_ALIASES.get(p, p)


def _get_jwt_secret() -> str:
    """Retorna JWT secret — NUNCA usa fallback inseguro em produção"""
    secret = os.getenv("JWT_SECRET")
    if not secret or secret == "secret_key_dev":
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            raise RuntimeError("JWT_SECRET não configurado para produção!")
        secret = "dev-only-secret-change-in-production"
    return secret


def create_jwt_token(user_id: int, email: str, plan: str) -> str:
    """Cria JWT com expiração de 24h"""
    payload: dict[str, Any] = {
        "user_id": user_id,
        "email": email,
        "plan": plan,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc),
        "jti": token_urlsafe(32),
    }
    return jwt.encode(  # type: ignore[no-untyped-call]
        payload,
        _get_jwt_secret(),
        algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
    )


def create_refresh_token(user_id: int, email: str) -> str:
    """Cria refresh token de longa duração (30 dias)."""
    payload: dict[str, Any] = {
        "user_id": user_id,
        "email": email,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
        "iat": datetime.now(timezone.utc),
        "jti": token_urlsafe(32),
    }
    return jwt.encode(  # type: ignore[no-untyped-call]
        payload,
        _get_jwt_secret(),
        algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
    )


def verify_jwt_token(token: str) -> dict[str, Any]:
    """Decodifica e valida JWT"""
    try:
        result: Any = jwt.decode(  # type: ignore[no-untyped-call]
            token,
            _get_jwt_secret(),
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")],
        )
        return dict(result) if result else {}
    except jwt.ExpiredSignatureError:  # type: ignore[attr-defined]
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:  # type: ignore[attr-defined]
        raise HTTPException(status_code=401, detail="Token inválido")


def _redirect_with_token(frontend_url: str, token: str) -> HTMLResponse:
    """Página mínima que salva token e redireciona ao frontend."""
    safe_frontend = frontend_url.rstrip("/") or "http://localhost:5173"
    html = f"""
    <html><body>
    <script>
        const token = {token!r};
        if (token) {{
            try {{ localStorage.setItem('access_token', token); }} catch (e) {{ console.error(e); }}
        }}
        const target = '{safe_frontend}/?mode=login#token=' + encodeURIComponent(token);
        window.location.replace(target);
    </script>
    Redirecionando...
    </body></html>
    """
    return HTMLResponse(content=html, status_code=200)


# ============================================================================
# DB SESSION HELPER
# ============================================================================

def _get_db_session() -> Session:
    """Retorna sessão do banco (para uso fora de Depends)"""
    return SessionLocal()


# ============================================================================
# DEPENDENCY — Autenticação via Bearer Token
# ============================================================================

async def get_current_user(authorization: Optional[str] = Header(None)) -> dict[str, Any]:
    """Extrai usuário do JWT e verifica no banco. Aplica trial enforcement."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = verify_jwt_token(parts[1])

    # Verificar se usuário ainda existe e está ativo
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == token_data.get("user_id")).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        if user.status != "active":  # type: ignore[union-attr]
            raise HTTPException(status_code=403, detail="Conta suspensa ou deletada")

        # ── Determinar role ──
        role = str(getattr(user, 'role', None) or 'user')

        # ── Resolver plano (freemium — sem trial) ──
        plan = _normalize_plan(user.plan)

        # Atualizar requests_today
        today = date.today()
        if user.requests_today_date != today:  # type: ignore[union-attr]
            user.requests_today = 1  # type: ignore[assignment]
            user.requests_today_date = today  # type: ignore[assignment]
        else:
            user.requests_today = (user.requests_today or 0) + 1  # type: ignore[assignment]
        db.commit()

        return {
            "user_id": user.id,
            "email": user.email,
            "plan": plan,
            "full_name": user.full_name,
            "role": role,
            "communication_preference": str(getattr(user, 'communication_preference', None) or 'email'),
            "requests_today": user.requests_today,
        }
    finally:
        db.close()


# ============================================================================
# PLANOS
# ============================================================================

PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "requests_per_day": 100,
        "requests_per_month": 2000,
        "concurrent_requests": 1,
        "features": ["contabilidade"],
        "price": 0,
    },
    "essencial": {
        "requests_per_day": 1000,
        "requests_per_month": 30000,
        "concurrent_requests": 5,
        "features": ["contabilidade", "clientes", "cobranca"],
        "price": 3990,
    },
    "profissional": {
        "requests_per_day": 10000,
        "requests_per_month": 300000,
        "concurrent_requests": 10,
        "features": ["contabilidade", "clientes", "cobranca", "agenda", "assistente"],
        "price": 6990,
    },
    "completo": {
        "requests_per_day": 999999,
        "requests_per_month": 999999,
        "concurrent_requests": 999999,
        "features": ["full_api", "dedicated_support", "custom_integration"],
        "price": 9990,
    },
    # Aliases retrocompatíveis
    "pro": {
        "requests_per_day": 1000,
        "requests_per_month": 30000,
        "concurrent_requests": 5,
        "features": ["contabilidade", "clientes", "cobranca"],
        "price": 3990,
    },
    "enterprise": {
        "requests_per_day": 999999,
        "requests_per_month": 999999,
        "concurrent_requests": 999999,
        "features": ["full_api", "dedicated_support", "custom_integration"],
        "price": 9990,
    },
}


# ============================================================================
# ROTAS
# ============================================================================

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserSignup):
    """
    Cadastro REAL — salva no banco com senha hashada.
    - Valida email único
    - Hash bcrypt 12 rounds
    - Cria JWT
    - Trial de 14 dias
    """
    if len(user_data.password) < 8:
        raise HTTPException(status_code=400, detail="Senha deve ter pelo menos 8 caracteres")

    db = _get_db_session()
    try:
        existing = db.query(User).filter(User.email == user_data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email já cadastrado")

        hashed = hash_password(user_data.password)
        # Validar preferência de comunicação
        comm_pref = user_data.communication_preference
        if comm_pref not in ("email", "whatsapp", "sms"):
            comm_pref = "email"

        new_user = User(
            email=user_data.email,
            password_hash=hashed,
            full_name=user_data.full_name,
            plan="free",
            status="active",
            last_login=datetime.now(timezone.utc),
            communication_preference=comm_pref,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        user_id = new_user.id  # type: ignore[union-attr]
        logger.info(f"Novo usuário cadastrado: {user_data.email} (ID: {user_id})")

        token = create_jwt_token(user_id, user_data.email, "free")
        refresh = create_refresh_token(user_id, user_data.email)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_id=str(user_id),
            email=user_data.email,
            plan="free",
            refresh_token=refresh,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro no signup: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar conta")
    finally:
        db.close()


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """
    Login REAL — valida email+senha no banco.
    """
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.email == credentials.email).first()

        if not user or not verify_password(credentials.password, str(user.password_hash)):
            raise HTTPException(status_code=401, detail="Email ou senha inválidos")

        if user.status != "active":  # type: ignore[union-attr]
            raise HTTPException(status_code=403, detail="Conta suspensa. Entre em contato com o suporte.")

        user.last_login = datetime.now(timezone.utc)  # type: ignore[assignment]
        db.commit()

        user_id = user.id  # type: ignore[union-attr]
        plan = _normalize_plan(user.plan)
        role = str(getattr(user, 'role', None) or 'user')

        token = create_jwt_token(user_id, credentials.email, plan)
        refresh = create_refresh_token(user_id, credentials.email)
        logger.info(f"Login bem-sucedido: {credentials.email} (role={role}, plan={plan})")

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_id=str(user_id),
            email=credentials.email,
            plan=plan,
            refresh_token=refresh,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no login: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno no login")
    finally:
        db.close()


@router.get("/me", response_model=UserProfile)
async def get_profile(current_user: dict[str, Any] = Depends(get_current_user)):
    """Perfil do usuário autenticado — dados REAIS do banco"""
    plan = str(current_user.get("plan", "free"))
    plan_config = PLANS.get(plan, PLANS["free"])
    requests_today = int(current_user.get("requests_today", 0))

    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        created_at = user.created_at if user else datetime.now(timezone.utc)  # type: ignore[union-attr]

        sub_expires = None
        if user:
            active_sub = (
                db.query(Subscription)
                .filter(Subscription.user_id == user.id, Subscription.status == "active")  # type: ignore[union-attr]
                .order_by(Subscription.created_at.desc())  # type: ignore[union-attr]
                .first()
            )
            if active_sub:
                sub_expires = active_sub.current_period_end  # type: ignore[union-attr]
    finally:
        db.close()

    return UserProfile(
        user_id=str(current_user["user_id"]),
        email=str(current_user["email"]),
        full_name=str(current_user.get("full_name", "")),
        plan=plan,
        role=str(current_user.get("role", "user")),
        communication_preference=str(current_user.get("communication_preference", "email")),
        created_at=created_at,  # type: ignore[arg-type]
        subscription_expires=sub_expires,
        requests_used=requests_today,
        requests_limit=int(plan_config["requests_per_day"]),
    )


@router.get("/my-limits")
async def get_my_limits(current_user: dict[str, Any] = Depends(get_current_user)):
    """Retorna limites do plano e uso atual do usuário."""
    from app.core.plan_limits import PLAN_LIMITS, resolve_plan

    plan_raw = str(current_user.get("plan", "free"))
    plan_enum = resolve_plan(plan_raw)
    limits = PLAN_LIMITS[plan_enum]
    uid = current_user["user_id"]

    db = _get_db_session()
    try:
        crm_count = db.query(Client).filter(
            Client.user_id == uid, Client.is_active == True  # noqa: E712
        ).count()

        start_month = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0,
        )
        invoice_count = db.query(Invoice).filter(
            Invoice.user_id == uid,
            Invoice.created_at >= start_month,
        ).count()

        from database.models import ChatMessage
        start_day = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        msg_count = db.query(ChatMessage).filter(
            ChatMessage.user_id == uid,
            ChatMessage.role == "user",
            ChatMessage.created_at >= start_day,
        ).count()
    finally:
        db.close()

    return {
        "plan": plan_enum.value,
        "display_name": limits["display_name"],
        "limits": {
            "crm_clients": {
                "max": limits["crm_clients"],
                "current": crm_count,
                "unlimited": limits["crm_clients"] == -1,
            },
            "invoices_per_month": {
                "max": limits["invoices_per_month"],
                "current": invoice_count,
                "unlimited": limits["invoices_per_month"] == -1,
            },
            "agent_messages_per_day": {
                "max": limits["agent_messages_per_day"],
                "current": msg_count,
                "unlimited": limits["agent_messages_per_day"] == -1,
            },
            "available_agents": limits["available_agents"],
        },
    }


# ============================================================================
# PREFERÊNCIAS DO USUÁRIO
# ============================================================================

class UpdatePreferencesRequest(BaseModel):
    communication_preference: Optional[str] = None  # email, whatsapp, sms


@router.put("/preferences")
async def update_preferences(
    prefs: UpdatePreferencesRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Atualizar preferências do usuário (forma de comunicação etc.)"""
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        valid_prefs = ("email", "whatsapp", "sms")
        if prefs.communication_preference:
            if prefs.communication_preference not in valid_prefs:
                raise HTTPException(
                    status_code=422,
                    detail=f"Opção inválida. Escolha: {', '.join(valid_prefs)}"
                )
            user.communication_preference = prefs.communication_preference  # type: ignore[assignment]

        db.commit()
        return {"status": "updated", "communication_preference": user.communication_preference}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao atualizar preferências: {e}")
        raise HTTPException(status_code=500, detail="Erro ao salvar preferências")
    finally:
        db.close()


# ============================================================================
# LGPD — EXPORTAÇÃO DE DADOS PESSOAIS
# ============================================================================

@router.get("/export-my-data")
async def export_my_data(current_user: dict[str, Any] = Depends(get_current_user)):
    """
    LGPD Art. 18 — Portabilidade: retorna TODOS os dados do usuário.
    Inclui: perfil, clientes, oportunidades, transações, agendamentos, interações.
    """
    uid = current_user["user_id"]
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        profile = {
            "id": user.id,  # type: ignore[union-attr]
            "email": user.email,  # type: ignore[union-attr]
            "full_name": user.full_name,  # type: ignore[union-attr]
            "plan": user.plan,  # type: ignore[union-attr]
            "created_at": str(user.created_at),  # type: ignore[union-attr]
            "lgpd_consent": user.lgpd_consent,  # type: ignore[union-attr]
            "lgpd_consent_at": str(user.lgpd_consent_at) if user.lgpd_consent_at else None,  # type: ignore[union-attr]
        }
    finally:
        db.close()

    # Buscar dados do CRM (com user_id filter)
    try:
        from database.crm_service import CRMService  # type: ignore[import]
        clients_data = CRMService.search_clients(query="", user_id=uid, limit=10000, offset=0)
        clients = clients_data.get("clients", [])

        # Buscar interações de cada cliente
        for c in clients:
            c["interactions"] = CRMService.get_interactions(c.get("id", 0), limit=1000)

        opportunities = CRMService.get_pipeline_summary(user_id=uid).get("pipeline", [])
        appointments = CRMService.get_appointments(user_id=uid).get("appointments", [])
        transactions = CRMService.get_financial_summary(user_id=uid)
    except Exception:
        clients, opportunities, appointments, transactions = [], [], [], {}

    return {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "clients": clients,
        "opportunities": opportunities,
        "appointments": appointments,
        "financial_summary": transactions,
        "notice": "Exportação conforme LGPD Art. 18 — Portabilidade de dados",
    }


# ============================================================================
# LGPD — EXCLUSÃO DE CONTA (DIREITO AO APAGAMENTO)
# ============================================================================

class DeleteAccountRequest(BaseModel):
    password: str
    confirm: bool = False


@router.delete("/delete-account")
async def delete_account(
    data: DeleteAccountRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    LGPD Art. 18 — Direito ao Apagamento.
    Exclui conta e anonimiza dados vinculados ao usuário.
    Requer confirmação de senha.
    """
    if not data.confirm:
        raise HTTPException(400, "Confirme a exclusão com confirm=true")

    uid = current_user["user_id"]
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(404, "Usuário não encontrado")

        # Verificar senha
        if not verify_password(data.password, user.password_hash):  # type: ignore[arg-type]
            raise HTTPException(403, "Senha incorreta")

        # Excluir dados relacionados no CRM
        try:
            from database.models import Client, Interaction, Opportunity, Appointment, Transaction, Invoice  # type: ignore[import]
            # Deletar clientes (cascade exclui interactions, opportunities, appointments)
            db.query(Client).filter(Client.user_id == uid).delete(synchronize_session=False)
            # Deletar subscriptions
            db.query(Subscription).filter(Subscription.user_id == uid).delete(synchronize_session=False)
        except Exception as e:
            logger.warning(f"Erro ao apagar dados CRM: {e}")

        # Anonimizar usuário (manter registro para integridade referencial)
        user.email = f"deleted_{uid}@anonimizado.nexus"  # type: ignore[assignment]
        user.full_name = "Usuário Removido"  # type: ignore[assignment]
        user.password_hash = "DELETED"  # type: ignore[assignment]
        user.status = "deleted"  # type: ignore[assignment]
        user.stripe_customer_id = None  # type: ignore[assignment]
        user.oauth_provider = None  # type: ignore[assignment]
        user.oauth_id = None  # type: ignore[assignment]
        user.lgpd_consent = False  # type: ignore[assignment]
        user.phone = None if hasattr(user, 'phone') else None  # type: ignore[assignment]

        db.commit()
        logger.info(f"Conta excluída/anonimizada: user_id={uid}")

        return {
            "status": "deleted",
            "message": "Conta excluída e dados anonimizados conforme LGPD Art. 18.",
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao excluir conta: {e}")
        raise HTTPException(500, "Erro ao excluir conta")
    finally:
        db.close()


# ============================================================================
# REFRESH TOKEN
# ============================================================================

class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(data: RefreshRequest):
    """
    Emite novo access_token a partir de um refresh_token válido.
    O refresh_token permanece válido até expirar (30 dias).
    """
    try:
        payload: Any = jwt.decode(  # type: ignore[no-untyped-call]
            data.refresh_token,
            _get_jwt_secret(),
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")],
        )
    except jwt.ExpiredSignatureError:  # type: ignore[attr-defined]
        raise HTTPException(401, "Refresh token expirado. Faça login novamente.")
    except jwt.InvalidTokenError:  # type: ignore[attr-defined]
        raise HTTPException(401, "Refresh token inválido")

    if payload.get("type") != "refresh":
        raise HTTPException(401, "Token não é um refresh token")

    user_id = payload.get("user_id")
    email = payload.get("email")

    # Verificar se usuário ainda existe e está ativo
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == user_id, User.status != "deleted").first()
        if not user:
            raise HTTPException(401, "Usuário não encontrado ou conta excluída")
        plan = _normalize_plan(user.plan)
    finally:
        db.close()

    new_access = create_jwt_token(user_id, email, plan)
    new_refresh = create_refresh_token(user_id, email)

    return TokenResponse(
        access_token=new_access,
        token_type="bearer",
        user_id=str(user_id),
        email=email,
        plan=plan,
        refresh_token=new_refresh,
    )


# ============================================================================
# STRIPE CHECKOUT
# ============================================================================

@router.post("/checkout", response_model=SubscriptionResponse)
async def create_checkout(
    payment: PaymentCheckout,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Checkout Stripe — cria sessão e vincula ao user_id."""
    import stripe  # type: ignore[import-untyped]

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe não configurado")

    # Normalizar nome do plano (aceitar aliases antigos)
    plan_key = _PLAN_ALIASES.get(payment.plan, payment.plan)
    _VALID_PAID_PLANS = {"essencial", "profissional", "completo"}
    if plan_key not in _VALID_PAID_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Plano inválido: '{payment.plan}'. Use: {', '.join(sorted(_VALID_PAID_PLANS))}",
        )

    try:
        price_in_cents = PLANS[plan_key]["price"]  # já está em centavos
        frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")

        _PLAN_DISPLAY_NAMES = {
            "essencial": "Essencial",
            "profissional": "Profissional",
            "completo": "Completo",
        }
        plan_display = _PLAN_DISPLAY_NAMES.get(plan_key, plan_key.capitalize())

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "brl",
                    "product_data": {
                        "name": f"NEXUS {plan_display}",
                        "description": f"Acesso ao plano {plan_display} do NEXUS",
                    },
                    "unit_amount": price_in_cents,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{frontend_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}/pricing",
            customer_email=payment.email,
            metadata={
                "plan": plan_key,
                "user_id": str(current_user["user_id"]),
                "email": payment.email,
            },
        )

        return SubscriptionResponse(
            status="pending",
            checkout_url=session.url or "",
            session_id=session.id,
        )
    except Exception as e:
        logger.error(f"Erro Stripe checkout: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar checkout: {str(e)}")


# ============================================================================
# STRIPE WEBHOOK — Processamento real de pagamentos
# ============================================================================

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """
    Webhook Stripe REAL:
    - checkout.session.completed → ativa plano
    - customer.subscription.deleted → cancela plano
    - invoice.payment_failed → loga falha
    """
    import stripe  # type: ignore[import-untyped]

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        elif os.getenv("ENVIRONMENT") == "production":
            raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET obrigatório em produção")
        else:
            import json
            event_data = json.loads(payload)
            event = stripe.Event.construct_from(event_data, stripe.api_key)
            logger.warning("⚠️ Webhook sem validação de assinatura (configure STRIPE_WEBHOOK_SECRET)")
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Assinatura inválida")

    event_type = event.type  # type: ignore[union-attr]
    logger.info(f"Stripe webhook: {event_type}")

    db = _get_db_session()
    try:
        if event_type == "checkout.session.completed":
            session_obj: Any = event.data.object  # type: ignore[union-attr]
            user_id = session_obj.metadata.get("user_id") if session_obj.metadata else None
            raw_plan = session_obj.metadata.get("plan", "free") if session_obj.metadata else "free"
            plan = _normalize_plan(raw_plan)

            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    user.plan = plan  # type: ignore[assignment]
                    if session_obj.customer:
                        user.stripe_customer_id = session_obj.customer  # type: ignore[assignment]

                    sub = Subscription(
                        user_id=int(user_id),
                        stripe_subscription_id=session_obj.subscription,
                        stripe_checkout_session_id=session_obj.id,
                        plan=plan,
                        status="active",
                        amount=float(PLANS.get(plan, {}).get("price", 0)),
                        current_period_start=datetime.now(timezone.utc),
                        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
                    )
                    db.add(sub)
                    db.commit()
                    logger.info(f"✅ Plano atualizado: User {user_id} → {plan}")

        elif event_type == "customer.subscription.deleted":
            sub_data: Any = event.data.object  # type: ignore[union-attr]
            sub = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == sub_data.id
            ).first()
            if sub:
                sub.status = "cancelled"  # type: ignore[assignment]
                sub.cancelled_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                user = db.query(User).filter(User.id == sub.user_id).first()
                if user:
                    user.plan = "free"  # type: ignore[assignment]
                db.commit()
                logger.info(f"Assinatura cancelada: {sub_data.id}")

        elif event_type == "invoice.payment_failed":
            invoice: Any = event.data.object  # type: ignore[union-attr]
            logger.warning(f"Pagamento falhou: customer {invoice.customer}")

        return {"status": "processed", "type": event_type}
    except Exception as e:
        db.rollback()
        logger.error(f"Erro webhook: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")
    finally:
        db.close()


@router.post("/verify-payment")
async def verify_payment(
    request_data: VerifyPaymentRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Verifica pagamento e atualiza plano"""
    import stripe  # type: ignore[import-untyped]

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe não configurado")

    try:
        session = stripe.checkout.Session.retrieve(request_data.session_id)
        if session.payment_status == "paid":
            raw_plan = session.metadata.get("plan", "free") if session.metadata else "free"
            plan = _normalize_plan(raw_plan)
            db = _get_db_session()
            try:
                user = db.query(User).filter(User.id == current_user["user_id"]).first()
                if user and user.plan != plan:
                    user.plan = plan  # type: ignore[assignment]
                    db.commit()
            finally:
                db.close()
            return {"status": "paid", "plan": plan, "email": current_user["email"]}
        return {"status": session.payment_status, "plan": "free"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# RATE LIMITING
# ============================================================================

async def check_rate_limit(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Valida limite de requisições por plano. Admins são isentos."""
    role = str(current_user.get("role", "user"))
    if role in ("admin", "superadmin"):
        return current_user  # Admin isento de rate limit

    plan = str(current_user.get("plan", "free"))
    daily_limit = PLANS[plan]["requests_per_day"]
    requests_today = int(current_user.get("requests_today", 0))
    if requests_today >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Limite de {daily_limit} requisições/dia atingido. Faça upgrade!",
        )
    return current_user


@router.get("/plans")
async def list_plans() -> dict[str, dict[str, Any]]:
    """Planos disponíveis"""
    return PLANS


class AdminSwitchPlanRequest(BaseModel):
    plan: str


@router.post("/admin/switch-plan")
async def admin_switch_plan(
    body: AdminSwitchPlanRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Admin pode trocar de plano instantaneamente para testes."""
    role = str(current_user.get("role", "user"))
    if role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Apenas administradores podem trocar de plano")

    plan = body.plan
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Plano inválido. Use: {', '.join(PLANS.keys())}")

    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        user.plan = plan  # type: ignore[assignment]
        db.commit()

        # Gerar novo token com o plano atualizado
        plan_config = PLANS.get(plan, PLANS["free"])
        new_token = jwt.encode(
            {
                "user_id": user.id,
                "email": user.email,
                "plan": plan,
                "role": role,
                "exp": datetime.now(timezone.utc) + timedelta(hours=24),
            },
            _get_jwt_secret(),
            algorithm="HS256",
        )

        return {
            "status": "ok",
            "plan": plan,
            "access_token": new_token,
            "requests_limit": plan_config["requests_per_day"],
            "features": plan_config["features"],
        }
    finally:
        db.close()


# ============================================================================
# OAUTH GOOGLE
# ============================================================================

@router.get("/google")
async def google_redirect():
    return RedirectResponse("/api/auth/google/start")


@router.get("/google/start")
async def google_start():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv(
        "GOOGLE_REDIRECT_URI",
        os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000") + "/api/auth/google/callback",
    )
    if not client_id:
        raise HTTPException(status_code=503, detail="GOOGLE_CLIENT_ID ausente")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth"
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return RedirectResponse(f"{url}?{query}")


@router.get("/google/callback")
async def google_callback(code: str | None = None, error: str | None = None):
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Faltou o code do Google")

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv(
        "GOOGLE_REDIRECT_URI",
        os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000") + "/api/auth/google/callback",
    )
    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")

    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Configure GOOGLE_CLIENT_ID/SECRET")

    token_resp = http_requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code, "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if not token_resp.ok:
        raise HTTPException(status_code=400, detail=f"Erro ao trocar code: {token_resp.text}")
    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Token não retornado pelo Google")

    user_resp = http_requests.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not user_resp.ok:
        raise HTTPException(status_code=400, detail=f"Erro userinfo: {user_resp.text}")
    info = user_resp.json()
    g_email = info.get("email", "")
    g_name = info.get("name", "Usuário Google")
    g_id = info.get("sub", "")

    db = _get_db_session()
    try:
        user = db.query(User).filter(User.email == g_email).first()
        if not user:
            user = User(
                email=g_email, password_hash=hash_password(token_urlsafe(32)),
                full_name=g_name, plan="free", status="active",
                oauth_provider="google", oauth_id=g_id,
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
                last_login=datetime.now(timezone.utc),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.last_login = datetime.now(timezone.utc)  # type: ignore[assignment]
            if not user.oauth_provider:
                user.oauth_provider = "google"  # type: ignore[assignment]
                user.oauth_id = g_id  # type: ignore[assignment]
            db.commit()
        token = create_jwt_token(user.id, g_email, _normalize_plan(user.plan))  # type: ignore[arg-type]
    finally:
        db.close()
    return _redirect_with_token(frontend_url, token)


# ============================================================================
# OAUTH FACEBOOK
# ============================================================================

@router.get("/facebook/start")
async def facebook_start():
    client_id = os.getenv("FACEBOOK_CLIENT_ID")
    redirect_uri = os.getenv(
        "FACEBOOK_REDIRECT_URI",
        os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000") + "/api/auth/facebook/callback",
    )
    if not client_id:
        raise HTTPException(status_code=503, detail="FACEBOOK_CLIENT_ID ausente")
    params = {
        "client_id": client_id, "redirect_uri": redirect_uri,
        "response_type": "code", "scope": "public_profile",
    }
    url = "https://www.facebook.com/v17.0/dialog/oauth"
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return RedirectResponse(f"{url}?{query}")


@router.get("/facebook/callback")
async def facebook_callback(code: str | None = None, error: str | None = None):
    if error:
        raise HTTPException(status_code=400, detail=f"Facebook OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Faltou o code do Facebook")

    client_id = os.getenv("FACEBOOK_CLIENT_ID")
    client_secret = os.getenv("FACEBOOK_CLIENT_SECRET")
    redirect_uri = os.getenv(
        "FACEBOOK_REDIRECT_URI",
        os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000") + "/api/auth/facebook/callback",
    )
    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")

    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Configure FACEBOOK_CLIENT_ID/SECRET")

    token_resp = http_requests.get(
        "https://graph.facebook.com/v17.0/oauth/access_token",
        params={"client_id": client_id, "client_secret": client_secret,
                "redirect_uri": redirect_uri, "code": code},
        timeout=10,
    )
    if not token_resp.ok:
        raise HTTPException(status_code=400, detail=f"Erro ao trocar code: {token_resp.text}")
    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Token não retornado pelo Facebook")

    user_resp = http_requests.get(
        "https://graph.facebook.com/me",
        params={"fields": "id,name,email", "access_token": access_token},
        timeout=10,
    )
    if not user_resp.ok:
        raise HTTPException(status_code=400, detail=f"Erro userinfo: {user_resp.text}")
    info = user_resp.json()
    fb_email = info.get("email") or f"fb_{info.get('id', 'x')}@facebook.com"
    fb_name = info.get("name", "Usuário Facebook")
    fb_id = info.get("id", "")

    db = _get_db_session()
    try:
        user = db.query(User).filter(User.email == fb_email).first()
        if not user:
            user = User(
                email=fb_email, password_hash=hash_password(token_urlsafe(32)),
                full_name=fb_name, plan="free", status="active",
                oauth_provider="facebook", oauth_id=fb_id,
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
                last_login=datetime.now(timezone.utc),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.last_login = datetime.now(timezone.utc)  # type: ignore[assignment]
            db.commit()
        token = create_jwt_token(user.id, fb_email, _normalize_plan(user.plan))  # type: ignore[arg-type]
    finally:
        db.close()
    return _redirect_with_token(frontend_url, token)


# ============================================================================
# RECUPERAÇÃO DE SENHA
# ============================================================================

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    """Envia email real de recuperação de senha (previne enumeração)."""
    logger.info(f"Recuperação de senha solicitada: {data.email}")

    # Sempre responde sucesso (previne enumeração de emails)
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.email == data.email).first()
        if user:
            # Gerar token e salvar no banco
            from app.api.email_service import generate_reset_token, send_password_reset_email  # type: ignore[import-unresolved]
            token = generate_reset_token()
            user.password_reset_token = token
            user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
            db.commit()
            # Enviar email (não-bloqueante para o response)
            send_password_reset_email(data.email, token)
    except Exception as e:
        logger.error(f"Erro no forgot-password: {e}")
    finally:
        db.close()

    return {
        "status": "sent",
        "message": "Se o email estiver cadastrado, enviaremos um link de recuperação.",
    }


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest):
    """Redefine senha via token enviado por email."""
    if len(data.new_password) < 8:
        raise HTTPException(400, "Senha deve ter pelo menos 8 caracteres")

    db = _get_db_session()
    try:
        user = db.query(User).filter(
            User.password_reset_token == data.token,
        ).first()

        if not user:
            raise HTTPException(400, "Token inválido ou expirado")

        # Verificar expiração
        if user.password_reset_expires:
            expires = user.password_reset_expires
            if hasattr(expires, 'tzinfo') and expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires:
                raise HTTPException(400, "Token expirado. Solicite um novo link.")

        # Atualizar senha
        user.password_hash = hash_password(data.new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        db.commit()

        logger.info(f"✅ Senha redefinida: {user.email}")
        return {"status": "ok", "message": "Senha redefinida com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro no reset-password: {e}")
        raise HTTPException(500, "Erro ao redefinir senha")
    finally:
        db.close()


# ============================================================================
# ALTERAR SENHA (usuário logado)
# ============================================================================

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password", tags=["authentication"])
async def change_password(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    """Altera a senha do usuário autenticado (precisa informar a senha atual)."""
    if len(data.new_password) < 8:
        raise HTTPException(400, "Nova senha deve ter pelo menos 8 caracteres")

    if data.current_password == data.new_password:
        raise HTTPException(400, "A nova senha deve ser diferente da atual")

    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(404, "Usuário não encontrado")

        if not verify_password(data.current_password, user.password_hash):
            raise HTTPException(401, "Senha atual incorreta")

        user.password_hash = hash_password(data.new_password)
        db.commit()

        logger.info(f"✅ Senha alterada pelo próprio usuário: {user.email}")
        return {"status": "ok", "message": "Senha alterada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro no change-password: {e}")
        raise HTTPException(500, "Erro ao alterar senha")
    finally:
        db.close()
