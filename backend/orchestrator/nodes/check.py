"""
Node CHECK — Verifica se o objetivo foi cumprido.
Decide se o loop continua (mais iterações) ou se a tarefa está concluída.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from backend.orchestrator.state import AgentState, TaskStatus

logger = logging.getLogger(__name__)


def check_node(state: AgentState) -> dict[str, Any]:
    """Avalia se a tarefa foi concluída com sucesso.
    
    Critérios de conclusão:
    1. Há uma final_response definida (agente respondeu ao usuário)
    2. Todas as ações foram executadas sem erro crítico
    3. Não excedeu max_iterations
    
    Se não concluída, incrementa iteração para novo ciclo sense→plan→act.
    """
    iteration = state.get("iteration", 0) + 1
    max_iterations = state.get("max_iterations", 10)
    results = state.get("action_results", [])
    final_response = state.get("final_response", "")
    error = state.get("error")
    
    logger.info(f"🔍 CHECK: iteração {iteration}/{max_iterations}")
    
    updates: dict[str, Any] = {
        "status": TaskStatus.CHECKING.value,
        "iteration": iteration,
        "updated_at": datetime.now().isoformat(),
    }
    
    # 1. Erro fatal → falha
    if error:
        updates["status"] = TaskStatus.FAILED.value
        if not final_response:
            updates["final_response"] = f"Desculpe, ocorreu um erro: {error}"
        logger.warning(f"❌ Tarefa falhou: {error}")
        return updates
    
    # 2. Limite de iterações → concluir forçado
    if iteration >= max_iterations:
        updates["status"] = TaskStatus.COMPLETED.value
        if not final_response:
            updates["final_response"] = (
                "Atingi o limite de tentativas. "
                "Aqui está o que consegui fazer até agora."
            )
        logger.warning(f"⚠️ Limite de iterações atingido ({max_iterations})")
        return updates
    
    # 3. Tem resposta final → concluído
    if final_response:
        updates["status"] = TaskStatus.COMPLETED.value
        logger.info("✅ Tarefa concluída com resposta")
        return updates
    
    # 4. Verificar resultados das ações
    if results:
        last_results = results[-len(state.get("planned_actions", [])) or 1:]
        all_success = all(r.get("success", False) for r in last_results)
        any_success = any(r.get("success", False) for r in last_results)
        
        if all_success:
            # Todas as ações ok, mas sem resposta → pedir ao planner gerar resposta
            updates["status"] = TaskStatus.COMPLETED.value
            # Montar resposta a partir dos resultados
            response_parts = []
            for r in last_results:
                output = r.get("output")
                if isinstance(output, dict) and "message" in output:
                    response_parts.append(output["message"])
                elif isinstance(output, dict) and "response" in output:
                    response_parts.append(output["response"])
            if response_parts:
                updates["final_response"] = "\n".join(response_parts)
            else:
                updates["final_response"] = "Pronto, tarefas executadas com sucesso."
            logger.info("✅ Todas as ações concluídas")
            return updates
        
        if not any_success:
            # Nenhuma ação funcionou → tentar novamente ou falhar
            if iteration >= 3:
                updates["status"] = TaskStatus.FAILED.value
                updates["final_response"] = (
                    "Não consegui completar nenhuma ação depois de várias tentativas. "
                    "Pode tentar reformular o pedido?"
                )
                logger.warning("❌ Falha persistente após 3 iterações")
                return updates
    
    # 5. Continuar loop (sense → plan → act → check)
    logger.info(f"🔄 Continuando loop (iteração {iteration})")
    return updates


def should_continue(state: AgentState) -> str:
    """Função de roteamento condicional para o grafo.
    
    Returns:
        "done" → tarefa concluída (sucesso ou falha)
        "continue" → novo ciclo do loop
        "wait_approval" → pausado para aprovação humana
    """
    status = state.get("status", "")
    
    if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
        return "done"
    
    if status == TaskStatus.WAITING_APPROVAL.value:
        return "wait_approval"
    
    return "continue"
