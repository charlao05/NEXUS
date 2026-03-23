"""
NEXUS — Serviço de verificação de limites (Freemium)
======================================================
Funções que verificam se o usuário atingiu os limites do plano.
Lançam HTTPException 403 com código estruturado se excedido.
Importado nos endpoints de CRM, invoices e agentes.
"""

from datetime import datetime, timezone
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)


def _get_session():
    """Obtém sessão do banco sob demanda."""
    from database.models import get_session
    return get_session()


def check_crm_limit(user: dict, contact_type: str | None = None) -> None:
    """Verifica se o usuário pode criar mais clientes ou fornecedores.
    Considera extra_client_slots (addon +10 por R$12,90 compra única).
    contact_type: None=conta todos, 'client'=só clientes, 'supplier'=só fornecedores."""
    # Admins são isentos de limites
    role = user.get("role", "user")
    if role in ("admin", "superadmin"):
        return

    from app.core.plan_limits import get_limit, is_unlimited
    from database.models import Client, User
    from sqlalchemy import or_

    plan = user.get("plan", "free")
    limit_key = "crm_suppliers" if contact_type == "supplier" else "crm_clients"
    limit = get_limit(plan, limit_key)
    if is_unlimited(limit):
        return

    uid = user.get("user_id", 0)
    session = _get_session()
    try:
        # Somar slots extras do addon (aplica a clientes E fornecedores)
        db_user = session.query(User).filter(User.id == uid).first()
        extra = getattr(db_user, 'extra_client_slots', 0) or 0
        effective_limit = limit + extra

        query = session.query(Client).filter(
            Client.user_id == uid,
            Client.is_active == True,  # noqa: E712
        )
        if contact_type == "supplier":
            query = query.filter(Client.contact_type == "supplier")
        elif contact_type == "client":
            query = query.filter(
                or_(Client.contact_type == "client", Client.contact_type.is_(None))
            )
        # Se contact_type=None, conta TODOS (backward compatible)

        count = query.count()
        label = "fornecedores" if contact_type == "supplier" else "clientes"
        if count >= effective_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "LIMIT_REACHED",
                    "resource": limit_key,
                    "limit": effective_limit,
                    "current": count,
                    "message": f"Seu plano permite até {effective_limit} {label}. "
                               f"Faça upgrade ou adicione mais por R$ 12,90 (compra única).",
                    "upgrade_url": "/pricing",
                },
            )
    finally:
        session.close()


def check_invoice_limit(user: dict) -> None:
    """Verifica se o usuário pode criar mais invoices neste mês."""
    # Admins são isentos de limites
    role = user.get("role", "user")
    if role in ("admin", "superadmin"):
        return

    from app.core.plan_limits import get_limit, is_unlimited
    from database.models import Invoice

    plan = user.get("plan", "free")
    limit = get_limit(plan, "invoices_per_month")
    if is_unlimited(limit):
        return

    uid = user.get("user_id", 0)
    start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0,
    )
    session = _get_session()
    try:
        count = session.query(Invoice).filter(
            Invoice.user_id == uid,
            Invoice.created_at >= start,
        ).count()
        if count >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "LIMIT_REACHED",
                    "resource": "invoices_per_month",
                    "limit": limit,
                    "current": count,
                    "message": f"Plano gratuito permite até {limit} cobranças "
                               f"por mês. Faça upgrade para continuar.",
                    "upgrade_url": "/pricing",
                },
            )
    finally:
        session.close()


def check_agent_access(user: dict, agent_id: str) -> None:
    """Verifica se o agente está disponível no plano do usuário."""
    from app.core.plan_limits import get_limit

    # Admins são isentos
    role = user.get("role", "user")
    if role in ("admin", "superadmin"):
        return

    plan = user.get("plan", "free")
    available = get_limit(plan, "available_agents")
    if available == "__all__":
        return

    # Mapear IDs de agente do frontend → backend
    from app.core.agent_aliases import resolve_agent_id
    resolved = resolve_agent_id(agent_id)

    if resolved not in available:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "AGENT_NOT_AVAILABLE",
                "resource": "agent",
                "agent": agent_id,
                "message": f"O agente '{agent_id}' não está disponível "
                           f"no plano gratuito. Faça upgrade para acessar.",
                "upgrade_url": "/pricing",
            },
        )


def check_agent_message_limit(user: dict) -> None:
    """Verifica se o usuário atingiu o limite de mensagens diárias.
    Considera bônus proporcional do addon de clientes extras."""
    from app.core.plan_limits import get_limit, is_unlimited
    from database.models import ChatMessage, User

    # Admins são isentos
    role = user.get("role", "user")
    if role in ("admin", "superadmin"):
        return

    plan = user.get("plan", "free")
    limit = get_limit(plan, "agent_messages_per_day")
    if is_unlimited(limit):
        return

    uid = user.get("user_id", 0)
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    session = _get_session()
    try:
        # Calcular limite efetivo com addon (proporcional a clientes extras)
        db_user = session.query(User).filter(User.id == uid).first()
        extra_slots = getattr(db_user, 'extra_client_slots', 0) or 0
        if extra_slots > 0:
            base_clients = get_limit(plan, "crm_clients")
            if base_clients and base_clients > 0:
                ratio = limit / base_clients  # ex: 50msgs / 5clients = 10
                effective_limit = limit + int(extra_slots * ratio)
            else:
                effective_limit = limit
        else:
            effective_limit = limit

        count = session.query(ChatMessage).filter(
            ChatMessage.user_id == uid,
            ChatMessage.role == "user",
            ChatMessage.created_at >= start,
        ).count()
        if count >= effective_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "LIMIT_REACHED",
                    "resource": "agent_messages_per_day",
                    "limit": effective_limit,
                    "current": count,
                    "message": f"Você atingiu o limite de {effective_limit} mensagens "
                               f"por dia. Faça upgrade ou aguarde amanhã.",
                    "upgrade_url": "/pricing",
                },
            )
    finally:
        session.close()
