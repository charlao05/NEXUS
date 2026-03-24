"""
NEXUS - Modelos de Banco de Dados (PostgreSQL + SQLAlchemy)
=============================================================
Persistência real para CRM profissional, agendamentos, finanças e automação.
Suporta PostgreSQL (produção) e SQLite (dev local) via DATABASE_URL.
"""

from datetime import datetime, date, timezone
from typing import Optional, Generator
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, DateTime,
    Date, Text, ForeignKey, Enum as SAEnum, JSON, Index, event
)
from sqlalchemy.orm import (
    DeclarativeBase, relationship, Session, sessionmaker
)
from sqlalchemy.pool import StaticPool
from pathlib import Path
import enum
import os
import logging

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Retorna datetime UTC timezone-aware (sem DeprecationWarning)"""
    return datetime.now(timezone.utc)

# ============================================================================
# DATABASE ENGINE — PostgreSQL (prod) / SQLite (dev)
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    # ── SQLite com caminho relativo: resolver em relação ao diretório backend ──
    if DATABASE_URL.startswith("sqlite:///./"):
        relative_path = DATABASE_URL.replace("sqlite:///./", "")
        abs_path = Path(__file__).parent.parent / relative_path
        DATABASE_URL = f"sqlite:///{abs_path}"
        engine = create_engine(
            DATABASE_URL,
            echo=False,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma_main(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
        logger.info(f"✅ Database: SQLite — {abs_path}")
    elif DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://"):
        # ── Produção: PostgreSQL ──
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=300,
        )
        logger.info("✅ Database: PostgreSQL (produção)")
    else:
        # Outra URL SQL (ex: sqlite absoluto, mysql, etc)
        _is_memory = ":memory:" in DATABASE_URL
        _extra_kw: dict = {}
        if _is_memory:
            # :memory: precisa de StaticPool para compartilhar o banco entre threads
            _extra_kw = {"poolclass": StaticPool, "pool_pre_ping": False}
        else:
            _extra_kw = {"pool_pre_ping": True}
        engine = create_engine(
            DATABASE_URL,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
            **_extra_kw,
        )
        logger.info(f"✅ Database: {DATABASE_URL.split('://')[0]}")
else:
    # ── Desenvolvimento: SQLite ──
    DB_PATH = Path(os.getenv("NEXUS_DB_PATH", str(Path(__file__).parent.parent / "data" / "nexus.db")))
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        echo=False,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    # WAL mode para melhor concorrência no SQLite
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
    logger.info(f"✅ Database: SQLite (dev) — {DB_PATH}")

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Retorna sessão do banco de dados (para FastAPI Depends)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """Retorna sessão direta (para uso fora de FastAPI)"""
    return SessionLocal()


class Base(DeclarativeBase):
    pass


# ============================================================================
# ENUMS
# ============================================================================

class UserPlan(str, enum.Enum):
    FREE = "free"
    ESSENCIAL = "essencial"
    PRO = "pro"            # alias legado → essencial
    PROFISSIONAL = "profissional"
    COMPLETO = "completo"
    ENTERPRISE = "enterprise"  # alias legado → completo


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class ClientSegment(str, enum.Enum):
    LEAD = "lead"
    PROSPECT = "prospect"
    STANDARD = "standard"
    PREMIUM = "premium"
    VIP = "vip"
    CHURNED = "churned"


class ClientSource(str, enum.Enum):
    MANUAL = "manual"
    INDICACAO = "indicacao"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    GOOGLE = "google"
    TELEGRAM = "telegram"
    SITE = "site"
    EVENTO = "evento"
    OUTRO = "outro"


class OpportunityStage(str, enum.Enum):
    PROSPECCAO = "prospeccao"
    QUALIFICACAO = "qualificacao"
    PROPOSTA = "proposta"
    NEGOCIACAO = "negociacao"
    FECHAMENTO = "fechamento"
    GANHO = "ganho"
    PERDIDO = "perdido"


class InteractionType(str, enum.Enum):
    LIGACAO = "ligacao"
    TELEGRAM = "telegram"
    EMAIL = "email"
    REUNIAO = "reuniao"
    VISITA = "visita"
    NOTA = "nota"
    AUTOMACAO = "automacao"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# MODELO DE USUÁRIO (Autenticação real)
# ============================================================================

class User(Base):
    """Usuário do sistema — autenticação real com bcrypt"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    full_name = Column(String(200), nullable=False)
    
    # Plano e assinatura
    plan = Column(String(20), default="free")  # free, pro, enterprise
    status = Column(String(20), default="active")  # active, suspended, deleted
    role = Column(String(20), default="user")  # user, admin, superadmin
    
    # Preferência de comunicação
    communication_preference = Column(String(20), default="email")  # email, telegram, sms

    # Telegram Bot
    telegram_chat_id = Column(String(50), nullable=True)
    telegram_connected_at = Column(DateTime, nullable=True)
    
    # OAuth (pode ter login social + senha)
    oauth_provider = Column(String(20), nullable=True)  # google, facebook
    oauth_id = Column(String(200), nullable=True)
    
    # Stripe
    stripe_customer_id = Column(String(100), nullable=True, unique=True)
    
    # Métricas de uso
    requests_today = Column(Integer, default=0)
    requests_today_date = Column(Date, nullable=True)
    
    # Trial (deprecated — mantido para compatibilidade com banco existente)
    trial_ends_at = Column(DateTime, nullable=True)

    # Freemium — data de conversão para plano pago
    plan_activated_at = Column(DateTime, nullable=True)
    
    # Email verification & password reset
    email_verified = Column(Boolean, default=False)
    password_reset_token = Column(String(200), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    
    # LGPD — consentimento
    lgpd_consent = Column(Boolean, default=False)
    lgpd_consent_at = Column(DateTime, nullable=True)
    lgpd_consent_ip = Column(String(45), nullable=True)
    
    # PIN de confirmação para ações sensíveis (opcional, se não definido usa senha de login)
    confirmation_pin_hash = Column(String(200), nullable=True)
    
    # Addon: slots extras de clientes/fornecedores (+10 cada, R$12,90 compra única)
    extra_client_slots = Column(Integer, default=0, nullable=True)
    addon_clients_purchased = Column(Boolean, default=False, nullable=True)
    
    # ── Perfil PF/PJ (preenchido após cadastro, na página de Perfil) ──────
    person_type = Column(String(2), nullable=True)        # PF ou PJ
    cpf = Column(String(14), nullable=True)               # 000.000.000-00
    cnpj = Column(String(18), nullable=True)              # 00.000.000/0000-00
    phone = Column(String(20), nullable=True)             # +55 11 99999-9999
    company_name = Column(String(200), nullable=True)     # Razão Social (PJ)
    trade_name = Column(String(200), nullable=True)       # Nome Fantasia (PJ)
    state_registration = Column(String(30), nullable=True) # Inscrição Estadual
    municipal_registration = Column(String(30), nullable=True)  # Inscrição Municipal
    address_street = Column(String(200), nullable=True)   # Logradouro
    address_number = Column(String(20), nullable=True)    # Número
    address_complement = Column(String(100), nullable=True)  # Complemento
    address_neighborhood = Column(String(100), nullable=True)  # Bairro
    address_city = Column(String(100), nullable=True)     # Cidade
    address_state = Column(String(2), nullable=True)      # UF (SP, RJ...)
    address_zip = Column(String(10), nullable=True)       # CEP
    birth_date = Column(Date, nullable=True)              # Data de nascimento (PF)
    business_type = Column(String(50), nullable=True)     # Tipo de negócio (MEI, ME, EPP...)
    
    # Datas
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relacionamentos
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_users_oauth", "oauth_provider", "oauth_id"),
    )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "plan": self.plan,
            "status": self.status,
            "role": self.role,
            "communication_preference": self.communication_preference,
            "oauth_provider": self.oauth_provider,
            "stripe_customer_id": self.stripe_customer_id,
            "requests_today": self.requests_today,
            "email_verified": self.email_verified,
            "lgpd_consent": self.lgpd_consent,
            "person_type": self.person_type,
            "cpf": self.cpf,
            "cnpj": self.cnpj,
            "phone": self.phone,
            "company_name": self.company_name,
            "trade_name": self.trade_name,
            "address_city": self.address_city,
            "address_state": self.address_state,
            "business_type": self.business_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class Subscription(Base):
    """Assinaturas Stripe — histórico de pagamentos"""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Stripe
    stripe_subscription_id = Column(String(100), nullable=True, unique=True)
    stripe_checkout_session_id = Column(String(200), nullable=True)
    
    plan = Column(String(20), nullable=False)  # pro, enterprise
    status = Column(String(20), default="active")  # active, cancelled, past_due, trialing
    
    # Período
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Valores
    amount = Column(Float, default=0.0)
    currency = Column(String(3), default="brl")
    
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    
    user = relationship("User", back_populates="subscriptions")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "plan": self.plan,
            "status": self.status,
            "stripe_subscription_id": self.stripe_subscription_id,
            "current_period_start": self.current_period_start.isoformat() if self.current_period_start else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "amount": self.amount,
            "currency": self.currency,
        }


# ============================================================================
# MODELOS CRM
# ============================================================================

class Client(Base):
    """Cliente — modelo central do CRM"""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    phone = Column(String(20), index=True)
    email = Column(String(200), index=True)
    cpf_cnpj = Column(String(20), unique=True, nullable=True)
    birth_date = Column(Date, nullable=True)
    address = Column(String(300))
    city = Column(String(100))
    state = Column(String(2))
    
    # Segmentação
    segment = Column(String(20), default="standard")
    source = Column(String(20), default="manual")
    tags = Column(JSON, default=list)
    
    # Tipo de contato: client (padrão) ou supplier (fornecedor)
    contact_type = Column(String(20), default="client")
    
    # Scores (calculados somente quando há histórico real)
    purchase_score = Column(Float, nullable=True, default=None)
    attendance_score = Column(Float, nullable=True, default=None)
    churn_risk = Column(Float, nullable=True, default=None)
    engagement_score = Column(Float, nullable=True, default=None)
    lifetime_value = Column(Float, default=0.0)
    
    # Métricas
    total_appointments = Column(Integer, default=0)
    total_purchases = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)
    avg_ticket = Column(Float, default=0.0)
    
    # Datas
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    last_interaction = Column(DateTime, nullable=True)
    last_purchase = Column(DateTime, nullable=True)
    
    # Notas
    notes = Column(Text, default="")
    
    # Estado
    is_active = Column(Boolean, default=True)
    
    # Relacionamentos
    interactions = relationship("Interaction", back_populates="client", cascade="all, delete-orphan")
    opportunities = relationship("Opportunity", back_populates="client", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="client", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_clients_segment", "segment"),
        Index("ix_clients_active", "is_active"),
        Index("ix_clients_user", "user_id"),
    )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "cpf_cnpj": self.cpf_cnpj,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "segment": self.segment,
            "source": self.source,
            "tags": self.tags or [],
            "lifetime_value": self.lifetime_value,
            "total_appointments": self.total_appointments,
            "total_purchases": self.total_purchases,
            "total_revenue": self.total_revenue,
            "avg_ticket": self.avg_ticket,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_interaction": self.last_interaction.isoformat() if self.last_interaction else None,
            "last_purchase": self.last_purchase.isoformat() if self.last_purchase else None,
            "is_active": self.is_active,
            "contact_type": self.contact_type or "client",
            "notes": self.notes,
        }


class Interaction(Base):
    """Histórico de interações com cliente"""
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    type = Column(String(20), default="nota")
    channel = Column(String(20), default="manual")  # telegram, email, telefone...
    summary = Column(Text, nullable=False)
    details = Column(Text, default="")
    sentiment = Column(String(10), default="neutral")  # positive, neutral, negative
    created_at = Column(DateTime, default=_utcnow)
    created_by = Column(String(100), default="system")
    
    client = relationship("Client", back_populates="interactions")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "type": self.type,
            "channel": self.channel,
            "summary": self.summary,
            "details": self.details,
            "sentiment": self.sentiment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Opportunity(Base):
    """Pipeline de vendas"""
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    value = Column(Float, default=0.0)
    stage = Column(String(20), default="prospeccao")
    probability = Column(Float, default=30.0)  # % de fechar
    expected_close = Column(Date, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    closed_at = Column(DateTime, nullable=True)
    is_won = Column(Boolean, nullable=True)  # None=aberto, True=ganho, False=perdido
    
    client = relationship("Client", back_populates="opportunities")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "title": self.title,
            "value": self.value,
            "stage": self.stage,
            "probability": self.probability,
            "expected_close": self.expected_close.isoformat() if self.expected_close else None,
            "is_won": self.is_won,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "notes": self.notes,
        }


class Appointment(Base):
    """Agendamentos com clientes"""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    scheduled_at = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, default=60)
    type = Column(String(30), default="reuniao")  # reuniao, consulta, ligacao, fiscal
    status = Column(String(20), default="scheduled")  # scheduled, confirmed, done, cancelled, no_show
    reminder_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    
    client = relationship("Client", back_populates="appointments")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_name": self.client.name if self.client else None,
            "title": self.title,
            "description": self.description,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "duration_minutes": self.duration_minutes,
            "type": self.type,
            "status": self.status,
            "reminder_sent": self.reminder_sent,
        }


# ============================================================================
# MODELO FINANCEIRO
# ============================================================================

class Transaction(Base):
    """Receitas e despesas"""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    type = Column(String(10), nullable=False)  # receita, despesa
    category = Column(String(50), default="geral")
    description = Column(String(300), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(30), default="nao_informado")  # pix, dinheiro, cartao_debito, cartao_credito, credito_proprio, fiado, boleto, transferencia, parcelado, entrada_parcelado, cheque, nao_informado
    date = Column(Date, nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True)
    is_recurring = Column(Boolean, default=False)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "category": self.category,
            "description": self.description,
            "amount": self.amount,
            "payment_method": self.payment_method or "nao_informado",
            "date": self.date.isoformat() if self.date else None,
            "client_id": self.client_id,
            "is_recurring": self.is_recurring,
            "notes": self.notes,
        }


class Invoice(Base):
    """Faturas / contas a receber"""
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    description = Column(String(300), nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    paid_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")  # pending, paid, overdue, cancelled
    reminders_sent = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "description": self.description,
            "amount": self.amount,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "status": self.status,
            "reminders_sent": self.reminders_sent,
        }


# ============================================================================
# MODELO DE AUTOMAÇÃO WEB (Assistente)
# ============================================================================

class ChatMessage(Base):
    """Histórico de mensagens do chat — persistência por usuário/agente"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_id = Column(String(30), nullable=False, index=True)  # agenda, clientes, financeiro...
    role = Column(String(10), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("ix_chat_user_agent", "user_id", "agent_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ActivityLog(Base):
    """Log de atividades do usuário — timeline para dashboard analytics"""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(50), nullable=False)  # login, signup, chat, create_client, create_appointment...
    agent_id = Column(String(30), nullable=True)
    details = Column(Text, default="")
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)

    def to_dict(self) -> dict:
        # Sufixo "Z" indica UTC — permite ao frontend converter para horário local
        ts = (self.created_at.isoformat() + "Z") if self.created_at else None
        return {
            "id": self.id,
            "action": self.action,
            "agent_id": self.agent_id,
            "details": self.details,
            "created_at": ts,
        }


class WebTask(Base):
    """Tarefa de automação web — requer aprovação humana"""
    __tablename__ = "web_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    target_url = Column(String(500), nullable=True)
    plan_json = Column(JSON, nullable=True)  # Plano gerado pelo LLM
    status = Column(String(20), default="pending")  # pending, approved, running, completed, failed, cancelled
    result = Column(Text, default="")
    error = Column(Text, default="")
    requested_by = Column(String(100), default="user")
    approved_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    approved_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "target_url": self.target_url,
            "plan": self.plan_json,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ============================================================================
# MODELOS DE INVENTÁRIO / ESTOQUE
# ============================================================================

class Product(Base):
    """Produto ou material — funciona para comércio, serviço e indústria"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    sku = Column(String(50), nullable=True)           # código do produto
    category = Column(String(100), nullable=True)     # categoria livre
    unit = Column(String(20), default="un")           # un, kg, lt, m, cx
    cost_price = Column(Float, default=0.0)           # preço de custo
    sale_price = Column(Float, default=0.0)           # preço de venda
    current_stock = Column(Float, default=0.0)        # saldo atual
    min_stock = Column(Float, default=0.0)            # estoque mínimo (alerta)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relacionamento
    movements = relationship("StockMovement", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_products_user", "user_id"),
        Index("ix_products_category", "category"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "sku": self.sku,
            "category": self.category,
            "unit": self.unit,
            "cost_price": self.cost_price,
            "sale_price": self.sale_price,
            "current_stock": self.current_stock,
            "min_stock": self.min_stock,
            "is_active": self.is_active,
            "needs_reorder": self.current_stock <= self.min_stock and self.min_stock > 0,
            "stock_value": round(self.current_stock * self.cost_price, 2),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class StockMovement(Base):
    """Movimentação de estoque — entrada ou saída"""
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    type = Column(String(10), nullable=False)   # "entrada" ou "saida"
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, default=0.0)     # preço unitário na movimentação
    total_value = Column(Float, default=0.0)    # quantity * unit_price
    reason = Column(String(200), nullable=True) # venda, compra, ajuste, uso, perda
    notes = Column(Text, nullable=True)
    reference_id = Column(String(100), nullable=True)  # id de invoice ou pedido
    created_at = Column(DateTime, default=_utcnow)

    product = relationship("Product", back_populates="movements")

    __table_args__ = (
        Index("ix_stock_movements_user", "user_id"),
        Index("ix_stock_movements_product", "product_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else None,
            "type": self.type,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total_value": self.total_value,
            "reason": self.reason,
            "notes": self.notes,
            "reference_id": self.reference_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# FEEDBACK DO USUÁRIO
# ============================================================================

class Feedback(Base):
    """Feedback do usuário para melhoria contínua"""
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_id = Column(String(30), nullable=True)       # Agente específico (ou null = geral)
    rating = Column(Integer, nullable=False)             # 1-5 estrelas
    category = Column(String(50), nullable=True)         # bug, sugestao, elogio, reclamacao
    message = Column(Text, nullable=True)                # Comentário livre
    page = Column(String(100), nullable=True)            # Página de onde veio
    created_at = Column(DateTime, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "rating": self.rating,
            "category": self.category,
            "message": self.message,
            "page": self.page,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# INICIALIZAÇÃO
# ============================================================================

def _auto_migrate_columns():
    """
    Migração automática: adiciona colunas que existem no model
    mas faltam no banco SQLite existente.
    Evita erros de 'no such column' ao evoluir o schema.
    """
    if "sqlite" not in str(engine.url):
        return  # Produção (PostgreSQL) deve usar Alembic

    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(engine)

    for table_name, table in Base.metadata.tables.items():
        try:
            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        except Exception:
            continue  # Tabela ainda não existe — create_all cuidará

        for col in table.columns:
            if col.name not in existing_cols:
                col_type = col.type.compile(engine.dialect)
                nullable = "NULL" if col.nullable else "NOT NULL"
                default = ""
                if col.default is not None and col.default.is_scalar:
                    default = f" DEFAULT {col.default.arg!r}"
                sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {col_type} {nullable}{default}'
                try:
                    with engine.begin() as conn:
                        conn.execute(text(sql))
                    logger.info(f"🔧 Auto-migrate: {table_name}.{col.name} ({col_type})")
                except Exception as e:
                    logger.warning(f"⚠️ Falha ao migrar {table_name}.{col.name}: {e}")

# ============================================================================
# MODELO DE IDEMPOTÊNCIA STRIPE
# ============================================================================
class StripeEvent(Base):
    """Registro de eventos Stripe processados — garante idempotência no webhook."""
    __tablename__ = "stripe_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    stripe_event_id = Column(String(200), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=True)
    processed_at = Column(DateTime, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "stripe_event_id": self.stripe_event_id,
            "event_type": self.event_type,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


def init_db():
    """Cria todas as tabelas se não existirem + migra colunas faltantes"""
    Base.metadata.create_all(bind=engine)
    _auto_migrate_columns()


# Auto-init na importação
init_db()
