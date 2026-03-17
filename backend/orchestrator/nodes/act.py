"""
Node ACT — Executor determinístico.
Executa ações aprovadas pelo firewall de políticas.
Cada tool é chamada de forma determinística (sem LLM).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from backend.orchestrator.state import (
    ActionResult,
    AgentState,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry de tools executáveis
# ---------------------------------------------------------------------------

_TOOL_REGISTRY: dict[str, Any] = {}


def register_tool(name: str):
    """Decorator para registrar uma tool executável."""
    def decorator(func):
        _TOOL_REGISTRY[name] = func
        return func
    return decorator


def get_registered_tools() -> list[str]:
    """Retorna nomes das tools registradas."""
    return list(_TOOL_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Tools CRM (acessam banco real)
# ---------------------------------------------------------------------------

@register_tool("crm_list_clients")
def _crm_list_clients(params: dict, user_id: int) -> Any:
    from backend.database.models import SessionLocal, Client
    db = SessionLocal()
    try:
        query = db.query(Client).filter(Client.user_id == user_id)
        active_filter = params.get("status")
        if active_filter == "active":
            query = query.filter(Client.is_active == True)  # noqa: E712
        elif active_filter == "inactive":
            query = query.filter(Client.is_active == False)  # noqa: E712
        limit = min(params.get("limit", 20), 50)
        clients = query.limit(limit).all()
        return [{"id": c.id, "name": c.name, "phone": c.phone, "is_active": c.is_active} for c in clients]
    finally:
        db.close()


@register_tool("crm_get_client")
def _crm_get_client(params: dict, user_id: int) -> Any:
    from backend.database.models import SessionLocal, Client
    db = SessionLocal()
    try:
        client = db.query(Client).filter(
            Client.id == params["client_id"],
            Client.user_id == user_id
        ).first()
        if not client:
            return {"error": "Cliente não encontrado"}
        return client.to_dict()
    finally:
        db.close()


@register_tool("crm_create_client")
def _crm_create_client(params: dict, user_id: int) -> Any:
    from backend.database.models import SessionLocal, Client
    db = SessionLocal()
    try:
        client = Client(
            user_id=user_id,
            name=params.get("name", "Sem nome"),
            email=params.get("email"),
            phone=params.get("phone"),
            segment=params.get("segment", "lead"),
            is_active=True,
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        return {"id": client.id, "name": client.name, "message": f"Cliente '{client.name}' criado"}
    finally:
        db.close()


@register_tool("crm_update_client")
def _crm_update_client(params: dict, user_id: int) -> Any:
    from backend.database.models import SessionLocal, Client
    db = SessionLocal()
    try:
        client = db.query(Client).filter(
            Client.id == params["client_id"],
            Client.user_id == user_id
        ).first()
        if not client:
            return {"error": "Cliente não encontrado"}
        fields = params.get("fields", {})
        for k, v in fields.items():
            if hasattr(client, k) and k not in ("id", "user_id", "created_at"):
                setattr(client, k, v)
        db.commit()
        return {"id": client.id, "message": f"Cliente '{client.name}' atualizado"}
    finally:
        db.close()


@register_tool("crm_delete_client")
def _crm_delete_client(params: dict, user_id: int) -> Any:
    from backend.database.models import SessionLocal, Client
    db = SessionLocal()
    try:
        client = db.query(Client).filter(
            Client.id == params["client_id"],
            Client.user_id == user_id
        ).first()
        if not client:
            return {"error": "Cliente não encontrado"}
        name = client.name
        db.delete(client)
        db.commit()
        return {"message": f"Cliente '{name}' removido"}
    finally:
        db.close()


@register_tool("crm_create_appointment")
def _crm_create_appointment(params: dict, user_id: int) -> Any:
    from backend.database.models import SessionLocal, Appointment
    from datetime import datetime as dt
    db = SessionLocal()
    try:
        date_str = params.get("date", "")
        time_str = params.get("time", "09:00")
        try:
            appt_date = dt.fromisoformat(f"{date_str}T{time_str}")
        except ValueError:
            appt_date = dt.now()
        
        appt = Appointment(
            user_id=user_id,
            client_id=params.get("client_id"),
            title=params.get("title", "Compromisso"),
            scheduled_at=appt_date,
            status="scheduled",
        )
        db.add(appt)
        db.commit()
        return {"id": appt.id, "message": f"Agendamento '{appt.title}' criado para {date_str} {time_str}"}
    finally:
        db.close()


@register_tool("crm_create_transaction")
def _crm_create_transaction(params: dict, user_id: int) -> Any:
    from backend.database.models import SessionLocal, Transaction
    from datetime import date, datetime as dt
    db = SessionLocal()
    try:
        # Parse date (YYYY-MM-DD) or use today
        date_str = params.get("date", "")
        try:
            tx_date = dt.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        except ValueError:
            tx_date = date.today()
        
        tx = Transaction(
            user_id=user_id,
            client_id=params.get("client_id"),
            type=params.get("type", "receita"),
            amount=float(params.get("amount", 0)),
            description=params.get("description", "Transação via orchestrator"),
            date=tx_date,
        )
        db.add(tx)
        db.commit()
        return {"id": tx.id, "message": f"Transação de R$ {tx.amount:.2f} registrada"}
    finally:
        db.close()


@register_tool("respond_to_user")
def _respond_to_user(params: dict, user_id: int) -> Any:
    """Pseudo-tool que define a resposta final."""
    return {"response": params.get("message", "")}


@register_tool("wait_for_user_login")
def _wait_for_user_login(params: dict, user_id: int) -> Any:
    """Pseudo-tool que pausa a automação para o usuário preencher dados sensíveis.
    
    O orquestrador detecta esta ação e entra em modo waiting_for_user.
    O browser permanece aberto para o usuário interagir manualmente.
    """
    message = params.get("message_to_user", "")
    if not message:
        message = (
            "Agora é a parte que só você pode fazer.\n"
            "Digite seus dados na tela do site e clique no botão de envio.\n"
            "Quando a próxima tela aparecer, volte aqui e clique em 'Continuar Automação'.\n"
            "O robô não vê nem guarda seu CPF ou senha."
        )
    return {"response": message, "waiting_for_user": True}


# ---------------------------------------------------------------------------
# Node principal
# ---------------------------------------------------------------------------

# Tools que recebem state (AgentState) ao invés de user_id
_BROWSER_TOOLS: set[str] = set()


def register_browser_tool(name: str):
    """Decorator para registrar uma browser tool (recebe state ao invés de user_id)."""
    def decorator(func):
        _TOOL_REGISTRY[name] = func
        _BROWSER_TOOLS.add(name)
        return func
    return decorator


def act_node(state: AgentState) -> dict[str, Any]:
    """Executa cada ação aprovada sequencialmente."""
    planned = state.get("planned_actions", [])
    user_id = state.get("user_id", 0)
    
    logger.info(f"⚡ ACT: executando {len(planned)} ações")
    
    updates: dict[str, Any] = {
        "status": TaskStatus.EXECUTING.value,
        "updated_at": datetime.now().isoformat(),
    }
    
    results: list[dict] = list(state.get("action_results", []))
    final_response = state.get("final_response", "")
    
    for i, action_dict in enumerate(planned):
        tool_name = action_dict.get("tool", "")
        params = action_dict.get("params", {})
        
        logger.info(f"  [{i+1}/{len(planned)}] Executando: {tool_name}")
        
        start = time.time()
        
        try:
            if tool_name not in _TOOL_REGISTRY:
                raise ValueError(f"Tool '{tool_name}' não registrada")
            
            tool_func = _TOOL_REGISTRY[tool_name]
            # Browser tools recebem state; CRM tools recebem user_id
            if tool_name in _BROWSER_TOOLS:
                output = tool_func(params, state)
            else:
                output = tool_func(params, user_id)
            
            duration = int((time.time() - start) * 1000)
            
            result = ActionResult(
                tool=tool_name,
                success=True,
                output=output,
                duration_ms=duration,
            )
            
            # Se é respond_to_user, capturar como resposta final
            if tool_name == "respond_to_user" and isinstance(output, dict):
                final_response = output.get("response", final_response)
            
            # Se é wait_for_user_login, capturar resposta e marcar para pausa
            if tool_name == "wait_for_user_login" and isinstance(output, dict):
                final_response = output.get("response", final_response)
                updates["status"] = TaskStatus.WAITING_FOR_USER.value
                updates["awaiting_user_input"] = True
                logger.info("⏸️ ACT: wait_for_user_login executada — pausando para input humano")
                # Parar execução: não executar mais ações após wait_for_user_login
                results.append(result.model_dump())
                break
                
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            logger.error(f"  ❌ Erro em {tool_name}: {e}")
            result = ActionResult(
                tool=tool_name,
                success=False,
                error=str(e),
                duration_ms=duration,
            )
        
        results.append(result.model_dump())
    
    updates["action_results"] = results
    updates["final_response"] = final_response
    updates["current_step"] = len(planned)
    
    succeeded = sum(1 for r in results if r.get("success"))
    logger.info(f"✅ ACT completo: {succeeded}/{len(planned)} ações bem-sucedidas")
    
    return updates
