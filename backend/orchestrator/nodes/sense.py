"""
Node SENSE — Coleta contexto do ambiente.
Para agentes CRM: busca dados do banco (clientes, agenda, financeiro).
Para browser agent: captura DOM/screenshot da página.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from backend.orchestrator.state import AgentState, TaskStatus

logger = logging.getLogger(__name__)


def sense_node(state: AgentState) -> dict[str, Any]:
    """Coleta contexto relevante para o agente tomar decisões.
    
    - CRM agents: busca dados reais do banco
    - Browser agent: captura estado da página
    - NF agent: carrega dados de vendas
    """
    agent_type = state.get("agent_type", "")
    user_id = state.get("user_id", 0)
    
    logger.info(f"👁️ SENSE: coletando contexto para agent={agent_type}, user={user_id}")
    
    updates: dict[str, Any] = {
        "status": TaskStatus.SENSING.value,
        "updated_at": datetime.now().isoformat(),
    }
    
    try:
        if agent_type in ("clientes", "financeiro", "contabilidade", "cobranca", "agenda"):
            updates["crm_context"] = _get_crm_context(user_id)
            
        elif agent_type == "browser":
            # Percepção DOM — estilo Steward/Comet
            # Na primeira iteração, apenas prepara config.
            # Em iterações subsequentes, captura estado real da página.
            iteration = state.get("iteration", 0)
            if iteration > 0:
                updates["page_observation"] = _get_browser_perception()
            else:
                site_config = state.get("site_config", {})
                updates["page_observation"] = (
                    f"Configuração do site carregada: {site_config.get('name', 'N/A')}. "
                    f"Aguardando primeira navegação."
                )
            
        elif agent_type == "nf":
            updates["crm_context"] = _get_nf_context(user_id)
            
        elif agent_type == "assistente":
            updates["crm_context"] = _get_assistant_context(user_id)
            
        else:
            updates["crm_context"] = "Nenhum contexto específico disponível."
            
    except Exception as e:
        logger.error(f"Erro no sense: {e}")
        updates["error"] = f"Erro ao coletar contexto: {e}"
        
    return updates


def _get_crm_context(user_id: int) -> str:
    """Busca contexto CRM do banco de dados."""
    try:
        from backend.database.models import SessionLocal, Client, Appointment, Transaction
        from sqlalchemy import func
        from datetime import date
        
        db = SessionLocal()
        try:
            # Contagem de clientes
            total = db.query(func.count(Client.id)).filter(
                Client.user_id == user_id
            ).scalar() or 0
            
            active = db.query(func.count(Client.id)).filter(
                Client.user_id == user_id,
                Client.is_active == True  # noqa: E712
            ).scalar() or 0
            
            # Agendamentos de hoje
            today = date.today()
            appts_today = db.query(func.count(Appointment.id)).filter(
                Appointment.user_id == user_id,
                func.date(Appointment.scheduled_at) == today
            ).scalar() or 0
            
            # Receita do mês
            from datetime import datetime as dt
            first_day = today.replace(day=1)
            month_revenue = db.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.type == "receita",
                Transaction.date >= first_day
            ).scalar() or 0
            
            lines = [
                f"👥 Você tem {total} clientes ({active} ativos)",
                f"📅 Hoje: {appts_today} compromissos",
                f"💰 Receita do mês: R$ {month_revenue:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            ]
            
            return "\n".join(lines)
        finally:
            db.close()
            
    except Exception as e:
        logger.warning(f"Não consegui acessar CRM: {e}")
        return "Dados do CRM indisponíveis no momento."


def _get_nf_context(user_id: int) -> str:
    """Contexto para emissão de NF."""
    try:
        from backend.database.models import SessionLocal, Client, Transaction
        from sqlalchemy import func
        
        db = SessionLocal()
        try:
            pending_invoices = db.query(func.count(Transaction.id)).filter(
                Transaction.user_id == user_id,
                Transaction.type == "income",
            ).scalar() or 0
            
            return f"📄 Transações registradas: {pending_invoices}"
        finally:
            db.close()
    except Exception as e:
        return f"Contexto NF indisponível: {e}"


def _get_assistant_context(user_id: int) -> str:
    """Contexto resumido para o assistente geral."""
    crm = _get_crm_context(user_id)
    return f"Resumo geral:\n{crm}"


def _get_browser_perception() -> str:
    """Captura percepção DOM da página aberta (se houver browser ativo).
    
    Usa a camada de percepção estilo Steward para extrair:
    - URL e título atuais
    - Elementos interativos filtrados e numerados
    - Tipo de página (form, table, login, etc.)
    """
    try:
        from backend.orchestrator.tools.browser import _browser_state
        from backend.browser.perception import get_compact_observation

        page = _browser_state.get("page")
        if page is None:
            return "Browser não está aberto. Navegue para uma URL primeiro."

        observation = get_compact_observation(page)
        return observation

    except Exception as e:
        logger.warning(f"Erro na percepção do browser: {e}")
        return f"Erro ao capturar percepção do browser: {e}"
