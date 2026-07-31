"""
NEXUS - Chat History & Analytics API
======================================
Persistência de conversas por usuário/agente + endpoints de analytics.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime, timedelta, timezone
import logging

from database.models import (  # type: ignore[import]
    ChatMessage, ActivityLog, User, Client, Appointment,
    Transaction, Opportunity, SessionLocal,
)
from app.api.auth import get_current_user  # type: ignore[import]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat-history"])
analytics_router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# IDs de agentes válidos para cross-agent queries
_VALID_AGENTS = {"agenda", "clientes", "contabilidade", "cobranca", "assistente"}

# Aliases: o frontend usa "financeiro" mas o backend armazena como "contabilidade"
_CHAT_AGENT_ALIAS: dict[str, str] = {
    "financeiro": "contabilidade",
    "documentos": "contabilidade",
}

# Mapeamento inverso para exibição no Dashboard
_DISPLAY_AGENT_NAME: dict[str, str] = {
    "contabilidade": "financeiro",
}


def _resolve_chat_agent_id(agent_id: str) -> str:
    """Resolve aliases de agente para o ID canônico usado no banco."""
    return _CHAT_AGENT_ALIAS.get(agent_id, agent_id)


# ============================================================================
# SCHEMAS
# ============================================================================

class ChatMessageIn(BaseModel):
    agent_id: str
    role: str  # user | assistant
    content: str


class ChatHistoryResponse(BaseModel):
    messages: list[dict[str, Any]]
    total: int
    agent_id: str


# ============================================================================
# DB HELPER
# ============================================================================

def _get_db():
    return SessionLocal()


# ============================================================================
# CHAT HISTORY ENDPOINTS
# ============================================================================


class CrossAgentHistoryResponse(BaseModel):
    """Resposta com histórico de todos os agentes."""
    agents: dict[str, list[dict[str, Any]]]
    total: int


@router.get("/history-all", response_model=CrossAgentHistoryResponse)
async def get_all_agents_history(
    limit: int = Query(default=10, le=50, description="Mensagens por agente"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retorna as últimas mensagens de TODOS os agentes do usuário.
    Usado para dar contexto cross-agent (cada agente sabe o que foi discutido nos outros)."""
    db = _get_db()
    try:
        agents_data: dict[str, list[dict[str, Any]]] = {}
        total = 0
        for agent_id in _VALID_AGENTS:
            messages = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.user_id == current_user["user_id"],
                    ChatMessage.agent_id == agent_id,
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
                .all()
            )
            if messages:
                msgs = [m.to_dict() for m in reversed(messages)]
                agents_data[agent_id] = msgs
                total += len(msgs)
        return CrossAgentHistoryResponse(agents=agents_data, total=total)
    finally:
        db.close()


@router.get("/history/{agent_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    agent_id: str,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retorna histórico de chat do usuário com um agente específico.
    Suporta paginação via limit/offset (MEDIUM FIX #16)."""
    original_id = agent_id
    agent_id = _resolve_chat_agent_id(agent_id)
    db = _get_db()
    try:
        # Contar total de mensagens para paginação
        total = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.user_id == current_user["user_id"],
                ChatMessage.agent_id == agent_id,
            )
            .count()
        )
        messages = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.user_id == current_user["user_id"],
                ChatMessage.agent_id == agent_id,
            )
            .order_by(ChatMessage.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        # Retornar em ordem cronológica
        msgs = [m.to_dict() for m in reversed(messages)]
        return ChatHistoryResponse(
            messages=msgs,
            total=total,
            agent_id=original_id,
        )
    finally:
        db.close()


@router.post("/save")
async def save_chat_message(
    msg: ChatMessageIn,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Salva uma mensagem do chat no histórico persistente"""
    if msg.role not in ("user", "assistant"):
        raise HTTPException(status_code=400, detail="role deve ser 'user' ou 'assistant'")

    resolved_agent_id = _resolve_chat_agent_id(msg.agent_id)
    db = _get_db()
    try:
        chat_msg = ChatMessage(
            user_id=current_user["user_id"],
            agent_id=resolved_agent_id,
            role=msg.role,
            content=msg.content,
        )
        db.add(chat_msg)
        db.commit()
        db.refresh(chat_msg)
        return {"id": chat_msg.id, "saved": True}
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar mensagem: {e}")
        raise HTTPException(status_code=500, detail="Erro ao salvar mensagem")
    finally:
        db.close()


@router.delete("/history/{agent_id}")
async def clear_chat_history(
    agent_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Limpa histórico de chat com um agente (SQLite + Redis)"""
    agent_id = _resolve_chat_agent_id(agent_id)
    db = _get_db()
    try:
        deleted = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.user_id == current_user["user_id"],
                ChatMessage.agent_id == agent_id,
            )
            .delete()
        )
        db.commit()

        # Limpar cache Redis também
        try:
            from app.services.chat_context import clear_context
            clear_context(current_user["user_id"], agent_id)
        except Exception:
            pass  # Redis indisponível não é bloqueante

        return {"cleared": True, "messages_deleted": deleted}
    finally:
        db.close()


# ============================================================================
# ACTIVITY LOG
# ============================================================================

def log_activity(
    user_id: int,
    action: str,
    agent_id: str | None = None,
    details: str = "",
    ip_address: str | None = None,
) -> None:
    """Registra atividade do usuário (chamado internamente)"""
    db = _get_db()
    try:
        entry = ActivityLog(
            user_id=user_id,
            action=action,
            agent_id=agent_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Falha ao registrar atividade: {e}")
    finally:
        db.close()


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@analytics_router.get("/dashboard")
async def analytics_dashboard(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Dashboard analytics consolidado — métricas reais do banco"""
    db = _get_db()
    try:
        user_id = current_user["user_id"]
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        # ⚠️ ARMADILHA DESARMADA EM 30/07/2026 — leia antes de mexer.
        #
        # DEZ queries abaixo NÃO filtravam por user_id: teriam somado receita,
        # despesa, pipeline, clientes, agendamentos, os dois gráficos e — a
        # pior — a barra de limite MEI (R$ 81.000) de TODOS os usuários.
        # (Eu corrigi sete na primeira passada e afirmei "as 7 queries". Eram
        # dez: as de gráfico e a de limite MEI ficaram de fora porque eu parei
        # de ler no ponto em que a lista que eu mesmo montara terminava.)
        #
        # ALCANCE REAL: nenhum. `analytics_router` NUNCA é montado em main.py —
        # esta função é código morto e o defeito jamais foi exposto a ninguém.
        # (Eu afirmei o contrário antes de verificar qual função servia
        # /api/crm/dashboard. Servia crm_routes.py:397, que sempre isolou.)
        #
        # POR QUE CORRIGIR MESMO ASSIM: frontend/src/pages/Dashboard.tsx JÁ
        # chama /api/analytics/dashboard. O gatilho está puxado — basta alguém
        # "consertar o dashboard" montando o router para o vazamento nascer
        # pronto, no mesmo commit. Ver AUDITORIA_NEXUS/20_CODIGO_MORTO.md.
        #
        # Não era arquitetura, era descuido: o user_id já estava na mão
        # (linha 256) e era usado corretamente na query de ActivityLog abaixo.
        #
        # ⚠️ Não existe teste cobrindo ESTA função — rota morta não se alcança
        # por HTTP. tests/test_isolamento_dashboard.py cobre a rota VIVA
        # (/api/crm/dashboard) e trava quem tentar servi-la a partir daqui.

        # 1) Total de clientes — SÓ os deste usuário
        total_clients = db.query(Client).filter(Client.user_id == user_id).count()
        active_clients = (
            db.query(Client)
            .filter(Client.user_id == user_id, Client.is_active == True)  # noqa: E712
            .count()
        )

        # 2) Receita do mês — SÓ deste usuário
        from sqlalchemy import func
        month_revenue = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == "receita",
                Transaction.date >= month_start.date(),
            )
            .scalar()
        ) or 0

        month_expenses = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == "despesa",
                Transaction.date >= month_start.date(),
            )
            .scalar()
        ) or 0

        # 3) Pipeline aberto — SÓ deste usuário.
        # Opportunity NÃO tem user_id próprio: o isolamento é INDIRETO, via
        # Client.user_id. Por isso o join é obrigatório — sem ele, soma o
        # pipeline de todo mundo.
        open_pipeline = (
            db.query(func.coalesce(func.sum(Opportunity.value), 0))
            .join(Client, Opportunity.client_id == Client.id)
            .filter(Client.user_id == user_id, Opportunity.is_won == None)  # noqa: E711
            .scalar()
        ) or 0

        open_opps = (
            db.query(Opportunity)
            .join(Client, Opportunity.client_id == Client.id)
            .filter(Client.user_id == user_id, Opportunity.is_won == None)  # noqa: E711
            .count()
        )

        # 4) Agendamentos hoje — SÓ deste usuário
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        appointments_today = (
            db.query(Appointment)
            .filter(
                Appointment.user_id == user_id,
                Appointment.scheduled_at >= today_start,
                Appointment.scheduled_at < today_end,
            )
            .count()
        )

        # 5) Atividades recentes (últimos 7 dias)
        recent_activities = (
            db.query(ActivityLog)
            .filter(
                ActivityLog.user_id == user_id,
                ActivityLog.created_at >= week_ago,
            )
            .order_by(ActivityLog.created_at.desc())
            .limit(20)
            .all()
        )

        # 6) Chat messages count por agente (últimos 7 dias)
        agent_chats = (
            db.query(
                ChatMessage.agent_id,
                func.count(ChatMessage.id).label("count"),
            )
            .filter(
                ChatMessage.user_id == user_id,
                ChatMessage.created_at >= week_ago,
            )
            .group_by(ChatMessage.agent_id)
            .all()
        )
        chat_by_agent = {
            _DISPLAY_AGENT_NAME.get(row.agent_id, row.agent_id): row.count
            for row in agent_chats
        }

        # 7) Receita por dia (últimos 30 dias) para gráfico — SÓ deste usuário
        thirty_days_ago = now - timedelta(days=30)
        daily_revenue = (
            db.query(
                Transaction.date,
                func.sum(Transaction.amount).label("total"),
            )
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == "receita",
                Transaction.date >= thirty_days_ago.date(),
            )
            .group_by(Transaction.date)
            .order_by(Transaction.date)
            .all()
        )
        revenue_chart = [
            {"date": str(row.date), "value": float(row.total)}
            for row in daily_revenue
        ]

        # 8) Clientes novos por semana (últimas 8 semanas) — SÓ deste usuário.
        #
        # Agrupamento feito em Python de propósito: a versão anterior usava
        # func.strftime("%Y-%W", ...), que é função do SQLite. Em Postgres
        # (Neon, que é o banco de produção) isso levanta ProgrammingError —
        # ou seja, montar este router derrubaria a rota com 500 em produção
        # enquanto passava nos testes locais em SQLite. São 8 semanas de
        # registros; não há ganho em empurrar o agrupamento para o banco.
        eight_weeks_ago = now - timedelta(weeks=8)
        novos_clientes = (
            db.query(Client.created_at)
            .filter(
                Client.user_id == user_id,
                Client.created_at >= eight_weeks_ago,
            )
            .all()
        )
        por_semana: dict[str, int] = {}
        for (criado_em,) in novos_clientes:
            if criado_em is None:
                continue
            ano, semana, _ = criado_em.isocalendar()
            chave = f"{ano}-{semana:02d}"
            por_semana[chave] = por_semana.get(chave, 0) + 1
        clients_chart = [
            {"week": semana, "count": qtd}
            for semana, qtd in sorted(por_semana.items())
        ]

        # 9) Limite MEI tracking — SÓ deste usuário.
        # É a query mais sensível do payload: alimenta a barra de progresso dos
        # R$ 81.000. Somando todos os tenants, o usuário veria a própria
        # margem de desenquadramento estourada por faturamento alheio.
        year_start = now.replace(month=1, day=1).date()
        year_revenue = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == "receita",
                Transaction.date >= year_start,
            )
            .scalar()
        ) or 0

        mei_limit = 81000.0
        mei_percent = round((float(year_revenue) / mei_limit) * 100, 1)

        return {
            "overview": {
                "total_clients": total_clients,
                "active_clients": active_clients,
                "month_revenue": float(month_revenue),
                "month_expenses": float(month_expenses),
                "month_profit": float(month_revenue) - float(month_expenses),
                "pipeline_value": float(open_pipeline),
                "pipeline_count": open_opps,
                "appointments_today": appointments_today,
            },
            "mei": {
                "year_revenue": float(year_revenue),
                "limit": mei_limit,
                "percent_used": mei_percent,
                "remaining": mei_limit - float(year_revenue),
            },
            "activity_timeline": [a.to_dict() for a in recent_activities],
            "chat_usage": chat_by_agent,
            "revenue_chart": revenue_chart,
            "clients_chart": clients_chart,
        }
    except Exception as e:
        logger.error(f"Erro analytics: {e}")
        raise HTTPException(status_code=500, detail="Erro ao gerar analytics")
    finally:
        db.close()


@analytics_router.get("/activity")
async def get_activity_timeline(
    days: int = Query(default=7, le=90),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Timeline de atividades do usuário"""
    db = _get_db()
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        activities = (
            db.query(ActivityLog)
            .filter(
                ActivityLog.user_id == current_user["user_id"],
                ActivityLog.created_at >= since,
            )
            .order_by(ActivityLog.created_at.desc())
            .limit(100)
            .all()
        )
        return {"activities": [a.to_dict() for a in activities], "days": days}
    finally:
        db.close()
