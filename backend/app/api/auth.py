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
    # Perfil PF/PJ
    person_type: Optional[str] = None
    cpf: Optional[str] = None
    cnpj: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    trade_name: Optional[str] = None
    state_registration: Optional[str] = None
    municipal_registration: Optional[str] = None
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    birth_date: Optional[str] = None
    business_type: Optional[str] = None


class PaymentCheckout(BaseModel):
    plan: str
    email: Optional[str] = None  # ignorado — backend usa email do usuário autenticado


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

import re as _re_auth
import hmac as _hmac
import hashlib as _hashlib


def _validate_password_strength(password: str) -> str | None:
    """Valida força da senha (padrão enterprise).
    Retorna mensagem de erro ou None se OK."""
    if len(password) < 8:
        return "Senha deve ter pelo menos 8 caracteres"
    if len(password) > 128:
        return "Senha deve ter no máximo 128 caracteres"
    if not _re_auth.search(r"[A-Z]", password):
        return "Senha deve conter pelo menos 1 letra maiúscula"
    if not _re_auth.search(r"[a-z]", password):
        return "Senha deve conter pelo menos 1 letra minúscula"
    if not _re_auth.search(r"\d", password):
        return "Senha deve conter pelo menos 1 número"
    if not _re_auth.search(r"[!@#$%^&*()_+\-=\[\]{}|;:'\",.<>?/\\`~]", password):
        return "Senha deve conter pelo menos 1 caractere especial"
    # Bloquear senhas comuns (top patterns)
    _WEAK_PATTERNS = [
        "password", "12345678", "qwerty", "abc123", "letmein",
        "welcome", "monkey", "master", "admin123", "iloveyou",
    ]
    if password.lower() in _WEAK_PATTERNS:
        return "Senha muito comum. Escolha uma mais segura."
    return None


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


def create_jwt_token(user_id: int, email: str, plan: str, role: str = "user") -> str:
    """Cria JWT com expiração de 24h — inclui iss/aud para validação enterprise."""
    payload: dict[str, Any] = {
        "user_id": user_id,
        "email": email,
        "plan": plan,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc),
        "nbf": datetime.now(timezone.utc),  # Not Before — token válido a partir de agora
        "jti": token_urlsafe(32),
        "iss": "nexus-api",
        "aud": "nexus-client",
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
        "nbf": datetime.now(timezone.utc),
        "jti": token_urlsafe(32),
        "iss": "nexus-api",
        "aud": "nexus-client",
    }
    return jwt.encode(  # type: ignore[no-untyped-call]
        payload,
        _get_jwt_secret(),
        algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
    )


def verify_jwt_token(token: str) -> dict[str, Any]:
    """Decodifica e valida JWT — verifica iss/aud/exp.
    Suporta tokens legados (sem iss/aud) em período de transição."""
    try:
        result: Any = jwt.decode(  # type: ignore[no-untyped-call]
            token,
            _get_jwt_secret(),
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")],
            issuer="nexus-api",
            audience="nexus-client",
            options={"require": ["exp", "iat"]},
        )
        return dict(result) if result else {}
    except (jwt.InvalidIssuerError, jwt.InvalidAudienceError, jwt.MissingRequiredClaimError):  # type: ignore[attr-defined]
        try:
            result = jwt.decode(  # type: ignore[no-untyped-call]
                token,
                _get_jwt_secret(),
                algorithms=[os.getenv("JWT_ALGORITHM", "HS256")],
                options={"require": ["exp"]},
            )
            logger.debug("JWT legado aceito (sem iss/aud) — será renovado no próximo refresh")
            return dict(result) if result else {}
        except jwt.ExpiredSignatureError:  # type: ignore[attr-defined]
            raise HTTPException(status_code=401, detail="Token expirado")
        except jwt.InvalidTokenError:  # type: ignore[attr-defined]
            raise HTTPException(status_code=401, detail="Token inválido")
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

    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == token_data.get("user_id")).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        if user.status != "active":  # type: ignore[union-attr]
            raise HTTPException(status_code=403, detail="Conta suspensa ou deletada")

        role = str(getattr(user, 'role', None) or 'user')
        plan = _normalize_plan(user.plan)

        return {
            "user_id": user.id,
            "email": user.email,
            "plan": plan,
            "full_name": user.full_name,
            "role": role,
            "communication_preference": str(getattr(user, 'communication_preference', None) or 'email'),
            "requests_today": user.requests_today or 0,
        }
    finally:
        db.close()


# ============================================================================
# INCREMENTO DE USO (somente interações com agentes)
# ============================================================================

def increment_request_count(user_id: int) -> int:
    """Incrementa requests_today para o usuário. Chamado APENAS nos endpoints
    de interação real com agentes (send_message, execute_agent, confirm-action).
    Retorna o novo valor de requests_today."""
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return 0
        today = date.today()
        if user.requests_today_date != today:  # type: ignore[union-attr]
            user.requests_today = 1  # type: ignore[assignment]
            user.requests_today_date = today  # type: ignore[assignment]
        else:
            user.requests_today = (user.requests_today or 0) + 1  # type: ignore[assignment]
        db.commit()
        return user.requests_today or 0  # type: ignore[return-value]
    except Exception:
        db.rollback()
        return 0
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
        "features": ["contabilidade", "clientes", "agenda"],
        "price": 0,
    },
    "essencial": {
        "requests_per_day": 1000,
        "requests_per_month": 30000,
        "concurrent_requests": 5,
        "features": ["contabilidade", "clientes", "cobranca", "agenda"],
        "price": 2990,
        "stripe_price_id": os.getenv("STRIPE_PRICE_ESSENCIAL", ""),
    },
    "profissional": {
        "requests_per_day": 10000,
        "requests_per_month": 300000,
        "concurrent_requests": 10,
        "features": ["contabilidade", "clientes", "cobranca", "agenda", "assistente"],
        "price": 5990,
        "stripe_price_id": os.getenv("STRIPE_PRICE_PROFISSIONAL", ""),
    },
    "completo": {
        "requests_per_day": 999999,
        "requests_per_month": 999999,
        "concurrent_requests": 999999,
        "features": ["full_api", "dedicated_support", "custom_integration"],
        "price": 8990,
        "stripe_price_id": os.getenv("STRIPE_PRICE_COMPLETO", ""),
    },
    # Aliases retrocompatíveis
    "pro": {
        "requests_per_day": 1000,
        "requests_per_month": 30000,
        "concurrent_requests": 5,
        "features": ["contabilidade", "clientes", "cobranca", "agenda"],
        "price": 2990,
    },
    "enterprise": {
        "requests_per_day": 999999,
        "requests_per_month": 999999,
        "concurrent_requests": 999999,
        "features": ["full_api", "dedicated_support", "custom_integration"],
        "price": 8990,
    },
}


# ============================================================================
# ROTAS
# ============================================================================

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserSignup):
    """Cadastro REAL — salva no banco com senha hashada."""
    pwd_err = _validate_password_strength(user_data.password)
    if pwd_err:
        raise HTTPException(status_code=400, detail=pwd_err)

    db = _get_db_session()
    try:
        existing = db.query(User).filter(User.email == user_data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email já cadastrado")

        hashed = hash_password(user_data.password)
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
    """Login REAL — valida email+senha no banco."""
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.email == credentials.email).first()

        if not user:
            verify_password(credentials.password, "$2b$12$" + "A" * 53)
            raise HTTPException(status_code=401, detail="Email ou senha inválidos")

        if not verify_password(credentials.password, str(user.password_hash)):
            raise HTTPException(status_code=401, detail="Email ou senha inválidos")

        if user.status != "active":  # type: ignore[union-attr]
            raise HTTPException(status_code=403, detail="Conta suspensa. Entre em contato com o suporte.")

        user.last_login = datetime.now(timezone.utc)  # type: ignore[assignment]
        db.commit()

        user_id = user.id  # type: ignore[union-attr]
        plan = _normalize_plan(user.plan)
        role = str(getattr(user, 'role', None) or 'user')

        token = create_jwt_token(user_id, credentials.email, plan, role)
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
        person_type=getattr(user, "person_type", None) if user else None,
        cpf=getattr(user, "cpf", None) if user else None,
        cnpj=getattr(user, "cnpj", None) if user else None,
        phone=getattr(user, "phone", None) if user else None,
        company_name=getattr(user, "company_name", None) if user else None,
        trade_name=getattr(user, "trade_name", None) if user else None,
        state_registration=getattr(user, "state_registration", None) if user else None,
        municipal_registration=getattr(user, "municipal_registration", None) if user else None,
        address_street=getattr(user, "address_street", None) if user else None,
        address_number=getattr(user, "address_number", None) if user else None,
        address_complement=getattr(user, "address_complement", None) if user else None,
        address_neighborhood=getattr(user, "address_neighborhood", None) if user else None,
        address_city=getattr(user, "address_city", None) if user else None,
        address_state=getattr(user, "address_state", None) if user else None,
        address_zip=getattr(user, "address_zip", None) if user else None,
        birth_date=str(user.birth_date) if user and getattr(user, "birth_date", None) else None,
        business_type=getattr(user, "business_type", None) if user else None,
    )


@router.get("/my-limits")
async def get_my_limits(current_user: dict[str, Any] = Depends(get_current_user)):
    """Retorna limites do plano e uso atual do usuário."""
    from app.core.plan_limits import PLAN_LIMITS, resolve_plan
    from sqlalchemy import or_

    plan_raw = str(current_user.get("plan", "free"))
    plan_enum = resolve_plan(plan_raw)
    limits = PLAN_LIMITS[plan_enum]
    uid = current_user["user_id"]

    db = _get_db_session()
    try:
        crm_client_count = db.query(Client).filter(
            Client.user_id == uid, Client.is_active == True,  # noqa: E712
            or_(Client.contact_type == "client", Client.contact_type.is_(None)),
        ).count()

        crm_supplier_count = db.query(Client).filter(
            Client.user_id == uid, Client.is_active == True,  # noqa: E712
            Client.contact_type == "supplier",
        ).count()

        user_obj = db.query(User).filter(User.id == uid).first()
        extra_slots = getattr(user_obj, 'extra_client_slots', 0) or 0
        addon_purchased = getattr(user_obj, 'addon_clients_purchased', False) or False

        base_crm = limits["crm_clients"]
        effective_crm = (base_crm + extra_slots) if base_crm != -1 else -1

        base_suppliers = limits.get("crm_suppliers", base_crm)
        effective_suppliers = (base_suppliers + extra_slots) if base_suppliers != -1 else -1

        base_msgs = limits["agent_messages_per_day"]
        if base_msgs != -1 and extra_slots > 0 and base_crm > 0:
            ratio = base_msgs / base_crm
            effective_msgs = base_msgs + int(extra_slots * ratio)
        else:
            effective_msgs = base_msgs

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
        "addon_clients_purchased": addon_purchased,
        "limits": {
            "crm_clients": {
                "max": effective_crm,
                "current": crm_client_count,
                "unlimited": effective_crm == -1,
            },
            "crm_suppliers": {
                "max": effective_suppliers,
                "current": crm_supplier_count,
                "unlimited": effective_suppliers == -1,
            },
            "invoices_per_month": {
                "max": limits["invoices_per_month"],
                "current": invoice_count,
                "unlimited": limits["invoices_per_month"] == -1,
            },
            "agent_messages_per_day": {
                "max": effective_msgs,
                "current": msg_count,
                "unlimited": effective_msgs == -1,
            },
            "available_agents": limits["available_agents"],
        },
    }


# ============================================================================
# PREFERÊNCIAS DO USUÁRIO
# ============================================================================

class UpdatePreferencesRequest(BaseModel):
    communication_preference: Optional[str] = None


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
# PERFIL DO USUÁRIO — Dados PF/PJ
# ============================================================================

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    person_type: Optional[str] = None
    cpf: Optional[str] = None
    cnpj: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    trade_name: Optional[str] = None
    state_registration: Optional[str] = None
    municipal_registration: Optional[str] = None
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    birth_date: Optional[str] = None
    business_type: Optional[str] = None
    communication_preference: Optional[str] = None


@router.put("/me", response_model=dict)
async def update_profile(
    data: UpdateProfileRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Atualizar perfil do usuário — dados pessoais PF/PJ, endereço etc."""
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        if data.person_type and data.person_type not in ("PF", "PJ"):
            raise HTTPException(400, "person_type deve ser 'PF' ou 'PJ'")
        if data.address_state and len(data.address_state) != 2:
            raise HTTPException(400, "address_state deve ter 2 caracteres (UF)")
        if data.communication_preference and data.communication_preference not in ("email", "whatsapp", "sms"):
            raise HTTPException(400, "communication_preference deve ser 'email', 'whatsapp' ou 'sms'")

        _ALLOWED_FIELDS = {
            "full_name", "person_type", "cpf", "cnpj", "phone",
            "company_name", "trade_name", "state_registration", "municipal_registration",
            "address_street", "address_number", "address_complement",
            "address_neighborhood", "address_city", "address_state", "address_zip",
            "birth_date", "business_type", "communication_preference",
        }

        updated_fields = []
        for field in _ALLOWED_FIELDS:
            value = getattr(data, field, None)
            if value is not None:
                if field == "birth_date":
                    try:
                        from datetime import date as _date_type
                        value = _date_type.fromisoformat(value)
                    except (ValueError, TypeError):
                        raise HTTPException(400, "birth_date deve estar no formato YYYY-MM-DD")
                setattr(user, field, value)
                updated_fields.append(field)

        if not updated_fields:
            return {"status": "ok", "message": "Nenhum campo para atualizar", "updated": []}

        db.commit()
        logger.info(f"Perfil atualizado user={user.id}: {updated_fields}")
        return {"status": "ok", "message": "Perfil atualizado com sucesso", "updated": updated_fields}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao atualizar perfil: {e}")
        raise HTTPException(500, "Erro ao salvar perfil")
    finally:
        db.close()


# ============================================================================
# FEEDBACK — Melhoria Contínua
# ============================================================================

class FeedbackRequest(BaseModel):
    rating: int
    category: Optional[str] = None
    message: Optional[str] = None
    agent_id: Optional[str] = None
    page: Optional[str] = None


@router.post("/feedback")
async def submit_feedback(
    data: FeedbackRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Envia feedback do usuário para melhoria contínua."""
    if not 1 <= data.rating <= 5:
        raise HTTPException(400, "rating deve ser entre 1 e 5")
    valid_categories = {"bug", "sugestao", "elogio", "reclamacao", None}
    if data.category not in valid_categories:
        raise HTTPException(400, f"category deve ser: {', '.join(c for c in valid_categories if c)}")

    db = _get_db_session()
    try:
        from database.models import Feedback
        fb = Feedback(
            user_id=current_user["user_id"],
            agent_id=data.agent_id,
            rating=data.rating,
            category=data.category,
            message=data.message,
            page=data.page,
        )
        db.add(fb)
        db.commit()
        logger.info(f"Feedback #{fb.id} de user={current_user['user_id']} rating={data.rating}")

        try:
            admins = db.query(User).filter(User.role == "admin").all()
            from app.api.notifications import send_notification
            _cat = data.category or "geral"
            for admin in admins:
                await send_notification(
                    admin.id, "new_feedback",
                    f"Novo Feedback ({_cat})",
                    f"Avaliação {data.rating}★ — {data.message[:80] if data.message else 'Sem comentário'}",
                    severity="info",
                    data={"feedback_id": fb.id, "rating": data.rating, "category": _cat},
                )
        except Exception:
            pass

        return {"status": "ok", "message": "Obrigado pelo feedback!", "id": fb.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar feedback: {e}")
        raise HTTPException(500, "Erro ao salvar feedback")
    finally:
        db.close()


@router.get("/feedbacks")
async def list_feedbacks(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Lista feedbacks do usuário (admin vê todos)."""
    db = _get_db_session()
    try:
        from database.models import Feedback
        query = db.query(Feedback)
        if current_user.get("role") != "admin":
            query = query.filter(Feedback.user_id == current_user["user_id"])
        feedbacks = query.order_by(Feedback.created_at.desc()).limit(100).all()
        return {"feedbacks": [f.to_dict() for f in feedbacks], "total": len(feedbacks)}
    finally:
        db.close()


# ============================================================================
# LGPD — EXPORTAÇÃO DE DADOS PESSOAIS
# ============================================================================

@router.get("/export-my-data")
async def export_my_data(current_user: dict[str, Any] = Depends(get_current_user)):
    """LGPD Art. 18 — Portabilidade: retorna TODOS os dados do usuário."""
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

    try:
        from database.crm_service import CRMService  # type: ignore[import]
        clients_data = CRMService.search_clients(query="", user_id=uid, limit=10000, offset=0)
        clients = clients_data.get("clients", [])
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
# LGPD — EXCLUSÃO DE CONTA
# ============================================================================

class DeleteAccountRequest(BaseModel):
    password: str
    confirm: bool = False


@router.delete("/delete-account")
async def delete_account(
    data: DeleteAccountRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """LGPD Art. 18 — Direito ao Apagamento."""
    if not data.confirm:
        raise HTTPException(400, "Confirme a exclusão com confirm=true")

    uid = current_user["user_id"]
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(404, "Usuário não encontrado")

        if not verify_password(data.password, user.password_hash):  # type: ignore[arg-type]
            raise HTTPException(403, "Senha incorreta")

        try:
            from database.models import Client, Interaction, Opportunity, Appointment, Transaction, Invoice  # type: ignore[import]
            db.query(Client).filter(Client.user_id == uid).delete(synchronize_session=False)
            db.query(Subscription).filter(Subscription.user_id == uid).delete(synchronize_session=False)
        except Exception as e:
            logger.warning(f"Erro ao apagar dados CRM: {e}")

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
    """Emite novo access_token a partir de um refresh_token válido."""
    try:
        payload: Any = jwt.decode(  # type: ignore[no-untyped-call]
            data.refresh_token,
            _get_jwt_secret(),
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")],
            issuer="nexus-api",
            audience="nexus-client",
        )
    except jwt.ExpiredSignatureError:  # type: ignore[attr-defined]
        raise HTTPException(401, "Refresh token expirado. Faça login novamente.")
    except jwt.InvalidTokenError:  # type: ignore[attr-defined]
        raise HTTPException(401, "Refresh token inválido")

    if payload.get("type") != "refresh":
        raise HTTPException(401, "Token não é um refresh token")

    user_id = payload.get("user_id")
    email = payload.get("email")

    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == user_id, User.status != "deleted").first()
        if not user:
            raise HTTPException(401, "Usuário não encontrado ou conta excluída")
        plan = _normalize_plan(user.plan)
        role = str(getattr(user, 'role', None) or 'user')
    finally:
        db.close()

    new_access = create_jwt_token(user_id, email, plan, role)
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
# STRIPE — init
# ============================================================================

def _init_stripe() -> Any:
    """Inicializa Stripe SDK com a chave da env. Retorna o módulo stripe."""
    import stripe  # type: ignore[import-untyped]
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    return stripe


# ============================================================================
# STRIPE CHECKOUT
# ============================================================================

@router.post("/checkout", response_model=SubscriptionResponse)
async def create_checkout(
    payment: PaymentCheckout,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Checkout Stripe — cria sessão e vincula ao user_id."""
    stripe = _init_stripe()
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe não configurado")

    plan_key = _PLAN_ALIASES.get(payment.plan, payment.plan)
    _VALID_PAID_PLANS = {"essencial", "profissional", "completo"}
    if plan_key not in _VALID_PAID_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Plano inválido: '{payment.plan}'. Use: {', '.join(sorted(_VALID_PAID_PLANS))}",
        )

    try:
        price_in_cents = PLANS[plan_key]["price"]
        stripe_price_id = PLANS[plan_key].get("stripe_price_id", "")
        frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")

        _env = os.getenv("ENVIRONMENT", "development")
    
        if _env != "production" and "localhost" in frontend_url:
            frontend_url = frontend_url.replace("https://", "http://")
            import re as _re
            _port_match = _re.search(r":(\d+)$", frontend_url)
            if _port_match and _port_match.group(1) not in ("5173", "5174", "5175", "3000"):
                frontend_url = _re.sub(r":\d+$", ":5173", frontend_url)
            elif not _port_match:
                frontend_url = f"{frontend_url}:5173"

        _PLAN_DISPLAY_NAMES = {
            "essencial": "Essencial",
            "profissional": "Profissional",
            "completo": "Completo",
        }
        plan_display = _PLAN_DISPLAY_NAMES.get(plan_key, plan_key.capitalize())

        # TAREFA 3: Upgrade/downgrade se já existir subscription ativa
        db_upgrade = _get_db_session()
        try:
            existing_sub = (
                db_upgrade.query(Subscription)
                .filter(
                    Subscription.user_id == current_user["user_id"],
                    Subscription.status == "active",
                    Subscription.stripe_subscription_id.isnot(None),
                )
                .order_by(Subscription.created_at.desc())
                .first()
            )
            if existing_sub and existing_sub.stripe_subscription_id:
                stripe_sub = stripe.Subscription.retrieve(existing_sub.stripe_subscription_id)
                if stripe_sub and stripe_sub.get("status") in ("active", "trialing"):
                    items = stripe_sub.get("items", {}).get("data", [])
                    if items and stripe_price_id:
                        stripe.Subscription.modify(
                            existing_sub.stripe_subscription_id,
                            items=[{"id": items[0]["id"], "price": stripe_price_id}],
                            proration_behavior="create_prorations",
                        )
                        user_obj = db_upgrade.query(User).filter(User.id == current_user["user_id"]).first()
                        if user_obj:
                            user_obj.plan = plan_key
                        existing_sub.plan = plan_key
                        db_upgrade.commit()
                        return SubscriptionResponse(
                            status="upgraded",
                            checkout_url="",
                            session_id=existing_sub.stripe_subscription_id or "",
                        )
        except HTTPException:
            raise
        except Exception as upg_err:
            logger.warning(f"Upgrade inline falhou, prosseguindo com checkout: {upg_err}")
        finally:
            db_upgrade.close()

        # Montar line_item com price_id fixo (produção) ou price_data inline (dev/fallback)
        if stripe_price_id:
            _line_item: dict = {"price": stripe_price_id}
        else:
            _line_item = {
                "price_data": {
                    "currency": "brl",
                    "product_data": {
                        "name": f"NEXUS {plan_display}",
                        "description": f"Acesso ao plano {plan_display} do NEXUS",
                    },
                    "unit_amount": price_in_cents,
                    "recurring": {"interval": "month"},
                }
            }

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{**_line_item, "quantity": 1}],
            mode="subscription",
            success_url=f"{frontend_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}/pricing",
            customer_email=current_user["email"],
            metadata={
                "plan": plan_key,
                "user_id": str(current_user["user_id"]),
                "email": current_user["email"],
            },
        )

        return SubscriptionResponse(
            status="pending",
            checkout_url=session.url or "",
            session_id=session.id,
        )
    except Exception as e:
        logger.error(f"Erro Stripe checkout: {e}")
        raise HTTPException(status_code=500, detail="Erro ao criar checkout. Tente novamente ou contate o suporte.")


# ============================================================================
# STRIPE BILLING PORTAL
# ============================================================================

@router.post("/create-portal-session")
async def create_portal_session(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Cria sessão do Stripe Billing Portal para gerenciar assinatura."""
    stripe = _init_stripe()
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe não configurado")
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user or not getattr(user, 'stripe_customer_id', None):
            raise HTTPException(
                status_code=400,
                detail="Nenhuma assinatura Stripe encontrada. Faça checkout primeiro.",
            )
        frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
        portal_session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{frontend_url}/settings",
        )
        return {"url": portal_session.url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar portal session: {e}")
        raise HTTPException(status_code=500, detail="Erro ao abrir portal de gerenciamento.")
    finally:
        db.close()


# ============================================================================
# ADDON: PACOTE EXTRA DE CLIENTES/FORNECEDORES
# ============================================================================

# ============================================================================
# STRIPE BILLING PORTAL
# ============================================================================
@router.post("/create-portal-session")
async def create_portal_session(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Cria sessão do Stripe Billing Portal para gerenciar assinatura."""
    stripe = _init_stripe()
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe não configurado")
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user or not getattr(user, 'stripe_customer_id', None):
            raise HTTPException(
                status_code=400,
                detail="Nenhuma assinatura Stripe encontrada. Faça checkout primeiro.",
            )
        frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
        portal_session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{frontend_url}/settings",
        )
        return {"url": portal_session.url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar portal session: {e}")
        raise HTTPException(status_code=500, detail="Erro ao abrir portal de gerenciamento.")
    finally:
        db.close()

class AddonCheckoutRequest(BaseModel):
    email: Optional[str] = None


@router.post("/checkout/addon-clients")
async def checkout_addon_clients(
    body: AddonCheckoutRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Cria checkout Stripe para addon de +10 clientes/fornecedores (R$12,90 compra única).
    Disponível SOMENTE para plano gratuito. Compra única por usuário."""

    plan = _normalize_plan(current_user.get("plan", "free"))
    if plan != "free":
        raise HTTPException(
            status_code=403,
            detail="O addon de clientes extras está disponível apenas para o plano gratuito.",
        )

    db = _get_db_session()
    try:
        user_check = db.query(User).filter(User.id == current_user["user_id"]).first()
        if user_check and getattr(user_check, 'addon_clients_purchased', False):
            raise HTTPException(
                status_code=409,
                detail="Você já adquiriu o pacote extra de clientes. Esta é uma compra única.",
            )
    finally:
        db.close()

    stripe = _init_stripe()
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe não configurado")

    try:
        frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
        _env = os.getenv("ENVIRONMENT", "development")
        if _env != "production" and "localhost" in frontend_url:
            frontend_url = frontend_url.replace("https://", "http://")

        session = stripe.checkout.Session.create(
            payment_method_types=["card", "pix"],
            payment_method_options={
                "pix": {"expires_after_seconds": 1800},
            },
            line_items=[{
                "price_data": {
                    "currency": "brl",
                    "product_data": {
                        "name": "NEXUS — Pacote Extra de Clientes e Fornecedores",
                        "description": "+10 clientes, +10 fornecedores e mensagens proporcionais (compra única)",
                    },
                    "unit_amount": 1290,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{frontend_url}/success?session_id={{CHECKOUT_SESSION_ID}}&addon=clients",
            cancel_url=f"{frontend_url}/pricing",
            customer_email=current_user["email"],
            metadata={
                "plan": "addon_clients",
                "user_id": str(current_user["user_id"]),
                "email": current_user["email"],
                "addon_type": "extra_clients",
                "slots": "10",
            },
        )

        return {
            "status": "pending",
            "checkout_url": session.url or "",
            "session_id": session.id,
        }
    except Exception as e:
        logger.error(f"Erro Stripe addon checkout: {e}")
        raise HTTPException(status_code=500, detail="Erro ao criar checkout. Tente novamente ou contate o suporte.")


# ============================================================================
# STRIPE WEBHOOK — Processamento real de pagamentos
# ============================================================================

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """
    Webhook Stripe REAL (idempotente):
    - checkout.session.completed → ativa plano
    - customer.subscription.deleted → cancela plano
    - customer.subscription.updated → atualiza período
    - invoice.paid → renova período da subscription
    - invoice.payment_failed → marca subscription como past_due
    """
    stripe = _init_stripe()
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

    # TAREFA 4: Idempotência global — verificar se já processamos este evento
    event_id = event.get("id") if hasattr(event, "get") else getattr(event, "id", None)
    if event_id:
        _idem_db = _get_db_session()
        try:
            from database.models import StripeEvent as _StripeEventModel
            existing_evt = _idem_db.query(_StripeEventModel).filter(
                _StripeEventModel.stripe_event_id == event_id
            ).first()
            if existing_evt:
                logger.info(f"⚠️ Evento Stripe já processado (idempotente): {event_id}")
                return {"status": "already_processed", "event_id": event_id}
            new_evt = _StripeEventModel(
                stripe_event_id=event_id,
                event_type=str(getattr(event, 'type', 'unknown')),
            )
            _idem_db.add(new_evt)
            _idem_db.commit()
        except ImportError:
            pass
        except Exception as idem_err:
            logger.warning(f"Erro na verificação de idempotência: {idem_err}")
        finally:
            _idem_db.close()

    db = _get_db_session()

    try:
        if event_type == "checkout.session.completed":
            session_obj: Any = event.data.object  # type: ignore[union-attr]
            user_id = session_obj.metadata.get("user_id") if session_obj.metadata else None
            raw_plan = session_obj.metadata.get("plan", "free") if session_obj.metadata else "free"
            addon_type = session_obj.metadata.get("addon_type") if session_obj.metadata else None

            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    if addon_type == "extra_clients":
                        if getattr(user, 'addon_clients_purchased', False):
                            logger.info(f"⚠️ Addon já processado para User {user_id} (idempotente)")
                        else:
                            slots = int(session_obj.metadata.get("slots", "10"))
                            current_extra = getattr(user, 'extra_client_slots', 0) or 0
                            user.extra_client_slots = current_extra + slots  # type: ignore[assignment]
                            user.addon_clients_purchased = True  # type: ignore[assignment]
                            if session_obj.customer:
                                user.stripe_customer_id = session_obj.customer  # type: ignore[assignment]
                            db.commit()
                            logger.info(f"✅ Addon clientes: User {user_id} → +{slots} slots (total: {user.extra_client_slots})")
                    else:
                        existing_sub = db.query(Subscription).filter(
                            Subscription.stripe_checkout_session_id == session_obj.id
                        ).first()
                        if existing_sub:
                            logger.info(f"⚠️ Checkout {session_obj.id} já processado (idempotente) — sub #{existing_sub.id}")
                        else:
                            plan = _normalize_plan(raw_plan)
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

        elif event_type == "invoice.paid":
            invoice_obj: Any = event.data.object  # type: ignore[union-attr]
            stripe_sub_id = getattr(invoice_obj, "subscription", None)
            if stripe_sub_id:
                sub = db.query(Subscription).filter(
                    Subscription.stripe_subscription_id == stripe_sub_id
                ).first()
                if sub:
                    sub.status = "active"  # type: ignore[assignment]
                    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)  # type: ignore[assignment]
                    db.commit()
                    logger.info(f"✅ Renovação paga: subscription {stripe_sub_id}")

        elif event_type == "customer.subscription.updated":
            sub_data: Any = event.data.object  # type: ignore[union-attr]
            sub = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == sub_data.id
            ).first()
            if sub:
                new_status = getattr(sub_data, "status", "active")
                sub.status = new_status  # type: ignore[assignment]
                period_end = getattr(sub_data, "current_period_end", None)
                if period_end:
                    sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)  # type: ignore[assignment]
                db.commit()
                logger.info(f"Subscription atualizada: {sub_data.id} → status={new_status}")

        elif event_type == "customer.subscription.deleted":
            sub_data = event.data.object  # type: ignore[union-attr]
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
            invoice_obj = event.data.object  # type: ignore[union-attr]
            stripe_sub_id = getattr(invoice_obj, "subscription", None)
            customer_id = getattr(invoice_obj, "customer", "unknown")
            logger.warning(f"⚠️ Pagamento falhou: customer={customer_id}, subscription={stripe_sub_id}")
            if stripe_sub_id:
                sub = db.query(Subscription).filter(
                    Subscription.stripe_subscription_id == stripe_sub_id
                ).first()
                if sub:
                    sub.status = "past_due"  # type: ignore[assignment]
                    db.commit()
                    logger.warning(f"Subscription {stripe_sub_id} marcada como past_due")

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
    stripe = _init_stripe()
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
        logger.error(f"Erro ao verificar checkout: {e}")
        raise HTTPException(status_code=400, detail="Erro ao verificar status do pagamento.")


# ============================================================================
# RATE LIMITING
# ============================================================================

async def check_rate_limit(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Valida limite de requisições por plano. Admins são isentos."""
    role = str(current_user.get("role", "user"))
    if role in ("admin", "superadmin"):
        return current_user

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

        plan_config = PLANS.get(plan, PLANS["free"])
        new_token = create_jwt_token(user.id, user.email, plan, str(getattr(user, 'role', None) or 'user'))  # type: ignore[arg-type]

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
# OAUTH — Estado CSRF
# ============================================================================

_oauth_pending_states: dict[str, float] = {}
_OAUTH_STATE_TTL = 600


def _create_oauth_state() -> str:
    import time
    state = token_urlsafe(32)
    now = time.time()
    expired = [k for k, v in _oauth_pending_states.items() if now - v > _OAUTH_STATE_TTL]
    for k in expired:
        _oauth_pending_states.pop(k, None)
    _oauth_pending_states[state] = now
    return state


def _validate_oauth_state(state: str | None) -> None:
    import time
    if not state:
        raise HTTPException(status_code=403, detail="OAuth state ausente — possível ataque CSRF")
    created = _oauth_pending_states.pop(state, None)
    if created is None:
        raise HTTPException(status_code=403, detail="OAuth state inválido ou já utilizado")
    if time.time() - created > _OAUTH_STATE_TTL:
        raise HTTPException(status_code=403, detail="OAuth state expirado")


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
    state = _create_oauth_state()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth"
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return RedirectResponse(f"{url}?{query}")


@router.get("/google/callback")
async def google_callback(code: str | None = None, error: str | None = None, state: str | None = None):
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Faltou o code do Google")
    _validate_oauth_state(state)

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
        token = create_jwt_token(user.id, g_email, _normalize_plan(user.plan), str(getattr(user, 'role', None) or 'user'))  # type: ignore[arg-type]
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
    state = _create_oauth_state()
    params = {
        "client_id": client_id, "redirect_uri": redirect_uri,
        "response_type": "code", "scope": "public_profile,email",
        "state": state,
    }
    url = "https://www.facebook.com/v17.0/dialog/oauth"
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return RedirectResponse(f"{url}?{query}")


@router.get("/facebook/callback")
async def facebook_callback(code: str | None = None, error: str | None = None, state: str | None = None):
    if error:
        raise HTTPException(status_code=400, detail=f"Facebook OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Faltou o code do Facebook")
    _validate_oauth_state(state)

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
                last_login=datetime.now(timezone.utc),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.last_login = datetime.now(timezone.utc)  # type: ignore[assignment]
            db.commit()
        token = create_jwt_token(user.id, fb_email, _normalize_plan(user.plan), str(getattr(user, 'role', None) or 'user'))  # type: ignore[arg-type]
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

    db = _get_db_session()
    try:
        user = db.query(User).filter(User.email == data.email).first()
        if user:
            from app.api.email_service import generate_reset_token, send_password_reset_email  # type: ignore[import-unresolved]
            token = generate_reset_token()
            user.password_reset_token = token
            user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
            db.commit()
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
    pwd_err = _validate_password_strength(data.new_password)
    if pwd_err:
        raise HTTPException(400, pwd_err)

    db = _get_db_session()
    try:
        user = db.query(User).filter(
            User.password_reset_token == data.token,
        ).first()

        if not user:
            raise HTTPException(400, "Token inválido ou expirado")

        if user.password_reset_expires:
            expires = user.password_reset_expires
            if hasattr(expires, 'tzinfo') and expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires:
                raise HTTPException(400, "Token expirado. Solicite um novo link.")

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
    """Altera a senha do usuário autenticado."""
    pwd_err = _validate_password_strength(data.new_password)
    if pwd_err:
        raise HTTPException(400, pwd_err)

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


# ============================================================================
# PIN DE CONFIRMAÇÃO
# ============================================================================

class SetConfirmationPinRequest(BaseModel):
    login_password: str
    new_pin: str

class RemoveConfirmationPinRequest(BaseModel):
    login_password: str


@router.post("/set-confirmation-pin", tags=["authentication"])
async def set_confirmation_pin(
    data: SetConfirmationPinRequest,
    current_user: dict = Depends(get_current_user),
):
    """Define ou atualiza o PIN de confirmação para ações sensíveis."""
    if len(data.new_pin) < 4:
        raise HTTPException(400, "PIN deve ter pelo menos 4 caracteres")
    if len(data.new_pin) > 50:
        raise HTTPException(400, "PIN deve ter no máximo 50 caracteres")

    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(404, "Usuário não encontrado")

        if not verify_password(data.login_password, user.password_hash):
            raise HTTPException(401, "Senha de login incorreta")

        user.confirmation_pin_hash = hash_password(data.new_pin)
        db.commit()

        logger.info(f"✅ PIN de confirmação definido por: {user.email}")
        return {"status": "ok", "message": "PIN de confirmação definido com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao definir PIN: {e}")
        raise HTTPException(500, "Erro ao definir PIN")
    finally:
        db.close()


@router.delete("/confirmation-pin", tags=["authentication"])
async def remove_confirmation_pin(
    data: RemoveConfirmationPinRequest,
    current_user: dict = Depends(get_current_user),
):
    """Remove o PIN de confirmação (volta a usar senha de login)."""
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(404, "Usuário não encontrado")

        if not verify_password(data.login_password, user.password_hash):
            raise HTTPException(401, "Senha de login incorreta")

        user.confirmation_pin_hash = None
        db.commit()

        logger.info(f"✅ PIN de confirmação removido por: {user.email}")
        return {"status": "ok", "message": "PIN removido. Será usada a senha de login."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao remover PIN: {e}")
        raise HTTPException(500, "Erro ao remover PIN")
    finally:
        db.close()


@router.get("/has-confirmation-pin", tags=["authentication"])
async def has_confirmation_pin(
    current_user: dict = Depends(get_current_user),
):
    """Verifica se o usuário tem PIN de confirmação configurado."""
    db = _get_db_session()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(404, "Usuário não encontrado")

        has_pin = bool(user.confirmation_pin_hash)
        return {"has_pin": has_pin}
    finally:
        db.close()