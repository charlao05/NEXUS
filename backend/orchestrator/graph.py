"""
Grafo principal do orquestrador LangGraph.
===========================================
Monta o StateGraph com o loop:

    sense → plan → policy ─┬─→ (wait_approval) ─→ act → check ─┬─→ END
                            │                                     │
                            └─→ act → check ─────────────────────►│
                                                (continue) ◄──────┘

Suporta:
- Checkpointing (SQLite por padrão)
- Human-in-the-loop via interrupt_before
- Até max_iterations loops antes de parar
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.orchestrator.nodes.act import act_node
from backend.orchestrator.nodes.check import check_node, should_continue
from backend.orchestrator.nodes.plan import plan_node
from backend.orchestrator.nodes.policy import policy_node
from backend.orchestrator.nodes.sense import sense_node
from backend.orchestrator.state import (
    AgentState,
    TaskStatus,
    create_initial_state,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Roteamento condicional pós-policy (aprovação humana)
# ---------------------------------------------------------------------------

def _route_after_policy(state: AgentState) -> str:
    """Decide se prossegue para execução ou pausa para aprovação."""
    if state.get("requires_approval"):
        return "wait_approval"
    status = state.get("status", "")
    if status == TaskStatus.FAILED.value:
        return "done"
    return "act"


def _route_after_check(state: AgentState) -> str:
    """Decide se o loop continua ou se a tarefa está concluída."""
    return should_continue(state)


# ---------------------------------------------------------------------------
# Nó de aprovação (human-in-the-loop placeholder)
# ---------------------------------------------------------------------------

def approval_gate_node(state: AgentState) -> dict[str, Any]:
    """Nó de passagem para aprovação humana.
    
    Quando o grafo é compilado com interrupt_before=["approval_gate"],
    a execução pausa aqui e o chamador pode inspecionar
    state["approval_message"], decidir, e chamar graph.update_state()
    para continuar.
    
    Se este nó for chamado diretamente (sem interrupt), ele continua
    a execução normalmente (presume aprovação automática se chegou aqui).
    """
    logger.info("✅ Aprovação concedida — prosseguindo com execução")
    return {
        "requires_approval": False,
        "status": TaskStatus.EXECUTING.value,
    }


# ---------------------------------------------------------------------------
# Construção do grafo
# ---------------------------------------------------------------------------

def create_orchestrator_graph(
    *,
    checkpointer: Any | None = None,
    interrupt_on_approval: bool = True,
) -> Any:
    """Cria e compila o StateGraph do orquestrador.
    
    Args:
        checkpointer: Checkpointer LangGraph (padrão: MemorySaver).
        interrupt_on_approval: Se True, pausa antes do approval_gate
            para permitir human-in-the-loop.
    
    Returns:
        Grafo compilado (RunnableGraph).
    """
    graph = StateGraph(AgentState)
    
    # --- Adicionar nós ---
    graph.add_node("sense", sense_node)
    graph.add_node("plan", plan_node)
    graph.add_node("policy", policy_node)
    graph.add_node("approval_gate", approval_gate_node)
    graph.add_node("act", act_node)
    graph.add_node("check", check_node)
    
    # --- Definir fluxo ---
    # Entry point → sense
    graph.set_entry_point("sense")
    
    # sense → plan (sempre)
    graph.add_edge("sense", "plan")
    
    # plan → policy (sempre)
    graph.add_edge("plan", "policy")
    
    # policy → condicional (aprovação ou act)
    graph.add_conditional_edges(
        "policy",
        _route_after_policy,
        {
            "act": "act",
            "wait_approval": "approval_gate",
            "done": END,
        },
    )
    
    # approval_gate → act (sempre — aprovação já concedida se chegou aqui)
    graph.add_edge("approval_gate", "act")
    
    # act → check (sempre)
    graph.add_edge("act", "check")
    
    # check → condicional (loop ou fim)
    graph.add_conditional_edges(
        "check",
        _route_after_check,
        {
            "done": END,
            "continue": "sense",
            "wait_approval": "approval_gate",
        },
    )
    
    # --- Compilar ---
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    compile_kwargs: dict[str, Any] = {"checkpointer": checkpointer}
    
    if interrupt_on_approval:
        compile_kwargs["interrupt_before"] = ["approval_gate"]
    
    compiled = graph.compile(**compile_kwargs)
    
    logger.info("🔧 Grafo do orquestrador compilado com sucesso")
    return compiled


# ---------------------------------------------------------------------------
# Função principal de execução
# ---------------------------------------------------------------------------

async def run_task(
    *,
    agent_type: str,
    user_id: int,
    goal: str,
    original_message: str = "",
    max_iterations: int = 10,
    max_steps: int = 20,
    site_config: dict[str, Any] | None = None,
    graph: Any | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Executa uma tarefa completa no orquestrador.
    
    Args:
        agent_type: Tipo do agente (clientes, financeiro, assistente, browser, nf).
        user_id: ID do usuário no banco.
        goal: Descrição do que o usuário quer.
        original_message: Mensagem original.
        max_iterations: Máximo de iterações do loop.
        max_steps: Máximo de passos de ação.
        site_config: Config do site (para browser agent).
        graph: Grafo pré-compilado (opcional).
        thread_id: ID da thread para checkpointing (opcional).
    
    Returns:
        Dicionário com final_response, status, action_results e metadata.
    """
    # ── Auto-import browser tools para que fiquem registradas no act_node ──
    if agent_type == "browser":
        try:
            import backend.orchestrator.tools.browser  # noqa: F401 — registra tools via decorators
            logger.debug("Browser tools importadas para registro no act_node")
        except Exception as e:
            logger.warning(f"Falha ao importar browser tools: {e}")

    task_id = f"task_{uuid.uuid4().hex[:12]}"
    _thread_id = thread_id or f"thread_{uuid.uuid4().hex[:12]}"
    
    initial_state = create_initial_state(
        task_id=task_id,
        agent_type=agent_type,
        user_id=user_id,
        goal=goal,
        original_message=original_message or goal,
        max_iterations=max_iterations,
        max_steps=max_steps,
        site_config=site_config,
    )
    
    if graph is None:
        graph = create_orchestrator_graph(interrupt_on_approval=False)
    
    config = {"configurable": {"thread_id": _thread_id}}
    
    logger.info(
        f"🚀 Iniciando tarefa {task_id} | "
        f"agente={agent_type} user={user_id} | "
        f"goal={goal[:80]}..."
    )
    
    # Executar o grafo
    final_state = None
    try:
        async for event in graph.astream(initial_state, config=config):
            # Cada event é {node_name: partial_state}
            for node_name, node_output in event.items():
                logger.debug(f"  ► {node_name}: {list(node_output.keys()) if isinstance(node_output, dict) else '...'}")
                final_state = node_output
    except Exception as e:
        logger.error(f"Erro na execução do grafo: {e}", exc_info=True)
        return {
            "task_id": task_id,
            "status": TaskStatus.FAILED.value,
            "final_response": f"Erro interno: {str(e)}",
            "action_results": [],
            "error": str(e),
        }
    
    # Obter estado final completo via checkpointer
    try:
        snapshot = graph.get_state(config)
        full_state = snapshot.values if snapshot else {}
    except Exception:
        full_state = final_state or {}
    
    status = full_state.get("status", TaskStatus.FAILED.value)
    final_response = full_state.get("final_response", "")
    action_results = full_state.get("action_results", [])
    
    logger.info(
        f"🏁 Tarefa {task_id} finalizada | "
        f"status={status} | "
        f"ações={len(action_results)} | "
        f"resposta={'sim' if final_response else 'não'}"
    )
    
    return {
        "task_id": task_id,
        "thread_id": _thread_id,
        "agent_type": agent_type,
        "status": status,
        "final_response": final_response,
        "action_results": action_results,
        "iterations": full_state.get("iteration", 0),
        "planned_actions": full_state.get("planned_actions", []),
        "policy_decisions": full_state.get("policy_decisions", []),
        "requires_approval": full_state.get("requires_approval", False),
        "approval_message": full_state.get("approval_message", ""),
        # Human-in-the-loop state
        "awaiting_user_input": full_state.get("awaiting_user_input", False),
        "awaiting_user_reason": full_state.get("awaiting_user_reason", ""),
        "resume_hint": full_state.get("resume_hint", ""),
    }
