"""
Node POLICY — Action Firewall.
Valida cada ação planejada contra as políticas de segurança.
Marca ações que requerem aprovação humana.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from backend.orchestrator.policies import (
    evaluate_plan,
    get_approval_summary,
    plan_requires_approval,
)
from backend.orchestrator.state import (
    AgentState,
    PlannedAction,
    TaskStatus,
)

logger = logging.getLogger(__name__)


def policy_node(state: AgentState) -> dict[str, Any]:
    """Valida ações planejadas contra políticas de segurança."""
    task_id = state.get("task_id", "unknown")
    planned_raw = state.get("planned_actions", [])
    
    logger.info(f"🛡️ POLICY: validando {len(planned_raw)} ações para task={task_id}")
    
    updates: dict[str, Any] = {
        "status": TaskStatus.VALIDATING.value,
        "updated_at": datetime.now().isoformat(),
    }
    
    try:
        # Converter dicts para PlannedAction
        actions = []
        for a in planned_raw:
            try:
                actions.append(PlannedAction(**a))
            except Exception as e:
                logger.warning(f"Ação inválida: {a} — {e}")
        
        if not actions:
            updates["error"] = "Nenhuma ação válida para avaliar"
            updates["status"] = TaskStatus.FAILED.value
            return updates
        
        # Avaliar contra políticas
        decisions = evaluate_plan(task_id, actions)
        updates["policy_decisions"] = [d.model_dump() for d in decisions]
        
        # Contar permitidas vs bloqueadas
        allowed = [d for d in decisions if d.allowed]
        blocked = [d for d in decisions if not d.allowed]
        
        if blocked:
            logger.warning(
                f"🚫 {len(blocked)} ações bloqueadas: "
                + ", ".join(f"{d.action.tool}: {d.reason}" for d in blocked)
            )
            # Registrar ações bloqueadas no estado para o planner ter feedback
            updates["blocked_actions_info"] = "; ".join(
                f"{d.action.tool}: {d.reason}" for d in blocked
            )
        else:
            updates["blocked_actions_info"] = ""
        
        # Filtrar plano para apenas ações permitidas
        allowed_actions = []
        for d in decisions:
            if d.allowed:
                action = d.action
                # Aplicar parâmetros modificados (ex: timeout reduzido)
                if d.modified_params:
                    action = action.model_copy(update={"params": d.modified_params})
                allowed_actions.append(action.model_dump())
        
        updates["planned_actions"] = allowed_actions
        
        # Verificar se precisa aprovação humana
        if plan_requires_approval(decisions):
            updates["requires_approval"] = True
            updates["approval_message"] = get_approval_summary(decisions)
            updates["status"] = TaskStatus.WAITING_APPROVAL.value
            logger.info("⏸️ Plano requer aprovação humana")
        else:
            updates["requires_approval"] = False
            
        logger.info(
            f"✅ Policy: {len(allowed_actions)} permitidas, "
            f"{len(blocked)} bloqueadas, "
            f"aprovação={'sim' if updates.get('requires_approval') else 'não'}"
        )
        
    except Exception as e:
        logger.error(f"Erro na validação de políticas: {e}")
        updates["error"] = f"Erro na política: {e}"
        updates["status"] = TaskStatus.FAILED.value
        
    return updates
