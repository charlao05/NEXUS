"""
NEXUS — Serviço de verificação de limites (Freemium)
======================================================
Funções que verificam se o usuário atingiu os limites do plano.
Lançam HTTPException 403 com código estruturado se excedido.
Importado nos endpoints de CRM, invoices e agentes.

TRIAL FREE (is_in_ai_trial):
Nos primeiros FREE_AI_TRIAL_DAYS dias após cadastro, o usuário Free
recebe trial_ai_messages_per_day msgs/dia e trial_automations_per_day
automações/dia para degustação. Após o trial: bloqueio total de IA.
O addon R$12,90 expande apenas CRM (clientes/fornecedores), não msgs.
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
    if role in ("admin", "superadmin") and not user.get("preview_mode"):
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
    if role in ("admin", "superadmin") and not user.get("preview_mode"):
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
    if role in ("admin", "superadmin") and not user.get("preview_mode"):
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

    LÓGICA TRIAL FREE:
    - Plano free dentro dos primeiros FREE_AI_TRIAL_DAYS dias:
      usa trial_ai_messages_per_day (10 msgs/dia) como limite efetivo.
    - Plano free após trial: limit=0 → bloqueia imediatamente (HTTP 403).
    - Planos pagos: usa agent_messages_per_day normalmente.
    - Addon R$12,90: expande CRM apenas, NÃO adiciona mensagens ao free.
    """
    from app.core.plan_limits import get_limit, is_unlimited, is_in_ai_trial
    from database.models import ChatMessage, User

    # Admins são isentos
    role = user.get("role", "user")
    if role in ("admin", "superadmin") and not user.get("preview_mode"):
        return

    plan = user.get("plan", "free")
    uid = user.get("user_id", 0)

    # --- Determinar limite efetivo ---
    if plan == "free":
        # Verificar se está no período de trial
        created_at = user.get("created_at")
        if created_at is None:
            # Buscar do banco se não vier no token
            session = _get_session()
            try:
                db_user = session.query(User).filter(User.id == uid).first()
                created_at = getattr(db_user, 'created_at', None) if db_user else None
            finally:
                session.close()

        if is_in_ai_trial(created_at):
            effective_limit = get_limit(plan, "trial_ai_messages_per_day")
            trial_active = True
        else:
            effective_limit = 0  # Fora do trial: zero acesso a IA
            trial_active = False

        if effective_limit == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "TRIAL_EXPIRED" if not trial_active else "LIMIT_REACHED",
                    "resource": "agent_messages_per_day",
                    "limit": 0,
                    "current": 0,
                    "message": (
                        "Seu período de degustação de 3 dias encerrou. "
                        "Assine um plano para continuar usando a IA."
                        if not trial_active else
                        "Limite de mensagens do trial atingido."
                    ),
                    "upgrade_url": "/pricing",
                },
            )
    else:
        # Planos pagos: limite do plano, sem bônus por addon de clientes
        effective_limit = get_limit(plan, "agent_messages_per_day")
        if is_unlimited(effective_limit):
            return

    # --- Contar mensagens do dia ---
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    session = _get_session()
    try:
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

def check_automation_limit(user: dict) -> None:
    """Verifica se o usuário atingiu o limite de automações diárias.

    LÓGICA TRIAL FREE:
    - Dentro dos primeiros FREE_AI_TRIAL_DAYS: trial_automations_per_day (1/dia).
    - Fora do trial: 0 automações → bloqueia imediatamente.
    - CUSTO: 1 automação ≈ R$0,0092 (gpt-4o-mini + Playwright).
      trial_automations_per_day=1 → custo máximo R$0,028/3 dias = R$0,028 total.
    """
    from app.core.plan_limits import get_limit, is_unlimited, is_in_ai_trial, AUTOMATION_MSG_WEIGHT
    from database.models import AutomationLog, User

    # Admins são isentos
    role = user.get("role", "user")
    if role in ("admin", "superadmin") and not user.get("preview_mode"):
        return

    plan = user.get("plan", "free")
    uid = user.get("user_id", 0)

    # --- Determinar limite efetivo ---
    if plan == "free":
        created_at = user.get("created_at")
        if created_at is None:
            session = _get_session()
            try:
                db_user = session.query(User).filter(User.id == uid).first()
                created_at = getattr(db_user, 'created_at', None) if db_user else None
            finally:
                session.close()

        if is_in_ai_trial(created_at):
            effective_limit = get_limit(plan, "trial_automations_per_day")
            trial_active = True
        else:
            effective_limit = 0
            trial_active = False

        if effective_limit == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "TRIAL_EXPIRED" if not trial_active else "LIMIT_REACHED",
                    "resource": "automations_per_day",
                    "limit": 0,
                    "current": 0,
                    "message": (
                        "Seu período de degustação encerrou. "
                        "Assine um plano para usar automações."
                        if not trial_active else
                        "Limite de automações do trial atingido."
                    ),
                    "upgrade_url": "/pricing",
                },
            )
    else:
        effective_limit = get_limit(plan, "automations_per_day")
        if is_unlimited(effective_limit):
            return

    # --- Contar automações do dia ---
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    session = _get_session()
    try:
        try:
            count = session.query(AutomationLog).filter(
                AutomationLog.user_id == uid,
                AutomationLog.created_at >= start,
            ).count()
        except Exception:
            # AutomationLog pode não existir ainda — liberar sem bloquear
            logger.warning("check_automation_limit: AutomationLog indisponível, liberando.")
            return

        if count >= effective_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "LIMIT_REACHED",
                    "resource": "automations_per_day",
                    "limit": effective_limit,
                    "current": count,
                    "message": f"Você atingiu o limite de {effective_limit} automação(ões) "
                               f"por dia. Faça upgrade para automatizar mais.",
                    "upgrade_url": "/pricing",
                },
            )
    finally:
        session.close()
