"""
Node CHECK — Verifica se o objetivo foi cumprido.
Decide se o loop continua (mais iterações) ou se a tarefa está concluída.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from orchestrator.state import AgentState, TaskStatus

logger = logging.getLogger(__name__)


# Keywords que indicam que a resposta pede input do usuário no browser
_USER_INPUT_KEYWORDS = [
    "credenciais", "login", "senha", "autenticação", "autenticar",
    "entrar com", "fazer login", "insira", "digite seus",
    "preencha seus", "usuário e senha", "faça login",
    "dados de acesso", "identificação", "seus dados", "efetuar login",
    "realizar login", "acesse com", "entre com", "tela de login",
    "formulário de login", "página de login",
]


def _response_needs_user_input(final_response: str, results: list[dict]) -> bool:
    """Detecta se a resposta final indica que o usuário precisa agir no browser."""
    resp_lower = final_response.lower()
    if any(kw in resp_lower for kw in _USER_INPUT_KEYWORDS):
        return True
    # Verificar se algum resultado de percepção identificou login page
    for r in results:
        output = r.get("output")
        if isinstance(output, dict):
            ps = output.get("page_state", {})
            if isinstance(ps, dict) and ps.get("page_type") == "login":
                return True
    return False


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
            # Montar mensagem útil com o progresso real
            succeeded = [r for r in results if r.get("success")]
            if succeeded:
                parts = ["Atingi o limite de tentativas, mas consegui executar alguns passos:\n"]
                for r in succeeded[-5:]:
                    output = r.get("output")
                    tool = r.get("tool", "?")
                    if isinstance(output, dict):
                        msg = output.get("message") or output.get("response") or ""
                        if msg:
                            parts.append(f"✅ {tool}: {msg[:150]}")
                if len(parts) > 1:
                    updates["final_response"] = "\n".join(parts)
                else:
                    updates["final_response"] = (
                        "Atingi o limite de tentativas. "
                        "Aqui está o que consegui fazer até agora."
                    )
            else:
                updates["final_response"] = (
                    "Atingi o limite de tentativas sem conseguir completar a tarefa. "
                    "Pode tentar novamente ou reformular o pedido?"
                )
        logger.warning(f"⚠️ Limite de iterações atingido ({max_iterations})")
        return updates
    
    # 3. Tem resposta final → concluído (ou waiting_for_user se browser + login)
    if final_response:
        # Para browser agent: se a resposta indica que o usuário precisa agir
        # (login, credenciais), NÃO marcar como concluído — marcar como waiting_for_user
        agent_type = state.get("agent_type", "")
        
        # Detecção explícita: se act_node já marcou como WAITING_FOR_USER (via wait_for_user_login)
        if state.get("status") == TaskStatus.WAITING_FOR_USER.value or state.get("awaiting_user_input"):
            updates["status"] = TaskStatus.WAITING_FOR_USER.value
            # Garantir que a mensagem de continuação está presente
            if "Continuar Automação" not in final_response:
                updates["final_response"] = (
                    final_response.rstrip()
                    + "\n\n🔄 Após completar sua parte no navegador, clique em **Continuar Automação** para eu prosseguir."
                )
            logger.info("⏸️ CHECK: Aguardando input do usuário (wait_for_user_login)")
            return updates
        
        # Detecção heurística: resposta menciona login/credenciais (fallback)
        if agent_type == "browser" and iteration <= 2 and _response_needs_user_input(final_response, results):
            updates["status"] = TaskStatus.WAITING_FOR_USER.value
            updates["final_response"] = (
                final_response.rstrip()
                + "\n\n🔄 Após inserir seus dados no navegador, clique em **Continuar Automação** para eu prosseguir."
            )
            logger.info("⏸️ Aguardando input do usuário no browser (login/credenciais)")
            return updates
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
        
        # Resultados mistos: algumas ações ok, outras não.
        # Se já rodamos 3+ ciclos com resultados parciais, encerrar com o que temos.
        if any_success and not all_success and iteration >= 3:
            updates["status"] = TaskStatus.COMPLETED.value
            response_parts: list[str] = []
            for r in results:
                if r.get("success"):
                    output = r.get("output")
                    if isinstance(output, dict):
                        msg = output.get("message") or output.get("response") or ""
                        if msg:
                            response_parts.append(f"✅ {msg[:150]}")
            if response_parts:
                updates["final_response"] = (
                    "Consegui completar parte das ações. Aqui está o resultado:\n\n"
                    + "\n".join(response_parts[-5:])
                )
            else:
                updates["final_response"] = (
                    "Algumas ações foram executadas mas não obtive todos os resultados esperados. "
                    "Tente novamente ou reformule o pedido."
                )
            logger.warning(f"⚠️ Resultados mistos persistentes — encerrando na iteração {iteration}")
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
    
    if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.WAITING_FOR_USER.value):
        return "done"
    
    if status == TaskStatus.WAITING_APPROVAL.value:
        return "wait_approval"
    
    return "continue"
