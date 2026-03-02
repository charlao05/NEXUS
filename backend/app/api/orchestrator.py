"""
Endpoints REST para o Orquestrador LangGraph.
==============================================
Expõe o novo orquestrador baseado em estado tipado,
com suporte a human-in-the-loop e observabilidade.

Rotas:
    POST /api/orchestrator/run         — Executar tarefa
    GET  /api/orchestrator/task/{id}   — Status de uma tarefa
    POST /api/orchestrator/approve/{id}— Aprovar tarefa pendente
    POST /api/orchestrator/reject/{id} — Rejeitar tarefa pendente
    GET  /api/orchestrator/health      — Health check do orquestrador
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestrator", tags=["Orchestrator"])

# ---------------------------------------------------------------------------
# Cache em memória de grafos compilados e resultados em andamento
# (Em produção, substituir por Redis/Postgres)
# ---------------------------------------------------------------------------
_compiled_graph: Any = None
_task_results: dict[str, dict[str, Any]] = {}
_pending_threads: dict[str, dict[str, Any]] = {}


def _get_graph() -> Any:
    """Obtém ou cria o grafo compilado (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        from backend.orchestrator.graph import create_orchestrator_graph
        # Importar tools para registrá-las no registry
        import backend.orchestrator.tools  # noqa: F401
        _compiled_graph = create_orchestrator_graph(interrupt_on_approval=True)
        logger.info("🔧 Grafo do orquestrador inicializado (singleton)")
    return _compiled_graph


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class OrchestratorRunRequest(BaseModel):
    """Requisição para executar uma tarefa no orquestrador."""
    agent_type: str = Field(
        description="Tipo de agente: clientes, financeiro, contabilidade, cobranca, agenda, assistente, browser"
    )
    goal: str = Field(description="O que o usuário quer realizar")
    user_id: int = Field(default=1, description="ID do usuário no banco")
    message: str = Field(default="", description="Mensagem original do usuário")
    max_iterations: int = Field(default=10, ge=1, le=50)
    max_steps: int = Field(default=20, ge=1, le=100)
    site_config: dict[str, Any] | None = Field(default=None, description="Config do site (browser agent)")


class OrchestratorRunResponse(BaseModel):
    """Resposta da execução do orquestrador."""
    task_id: str
    thread_id: str
    status: str
    final_response: str = ""
    action_results: list[dict[str, Any]] = []
    iterations: int = 0
    requires_approval: bool = False
    approval_message: str = ""


class ApprovalRequest(BaseModel):
    """Requisição de aprovação/rejeição."""
    approved: bool = True
    reason: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/run", response_model=OrchestratorRunResponse)
async def run_orchestrator(request: OrchestratorRunRequest) -> OrchestratorRunResponse:
    """Executa uma tarefa completa no orquestrador LangGraph.

    O orquestrador segue o loop: sense → plan → policy → act → check.
    Se uma ação requer aprovação humana, retorna com `requires_approval=True`
    e o chamador deve chamar POST /approve/{task_id} para prosseguir.
    """
    try:
        from backend.orchestrator.graph import run_task

        result = await run_task(
            agent_type=request.agent_type,
            user_id=request.user_id,
            goal=request.goal,
            original_message=request.message or request.goal,
            max_iterations=request.max_iterations,
            max_steps=request.max_steps,
            site_config=request.site_config,
            graph=_get_graph(),
        )

        task_id = result.get("task_id", "unknown")
        _task_results[task_id] = result

        # Se requer aprovação, guardar thread_id para continuar depois
        if result.get("requires_approval"):
            _pending_threads[task_id] = {
                "thread_id": result.get("thread_id", ""),
                "approval_message": result.get("approval_message", ""),
                "agent_type": request.agent_type,
            }

        return OrchestratorRunResponse(
            task_id=task_id,
            thread_id=result.get("thread_id", ""),
            status=result.get("status", "unknown"),
            final_response=result.get("final_response", ""),
            action_results=result.get("action_results", []),
            iterations=result.get("iterations", 0),
            requires_approval=result.get("requires_approval", False),
            approval_message=result.get("approval_message", ""),
        )

    except Exception as e:
        logger.error(f"Erro ao executar orquestrador: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro no orquestrador: {str(e)}")


@router.get("/task/{task_id}")
async def get_task_status(task_id: str) -> dict[str, Any]:
    """Retorna o status e resultados de uma tarefa."""
    if task_id not in _task_results:
        raise HTTPException(status_code=404, detail=f"Tarefa {task_id} não encontrada")
    return _task_results[task_id]


@router.post("/approve/{task_id}")
async def approve_task(task_id: str, request: ApprovalRequest) -> dict[str, Any]:
    """Aprova ou rejeita uma tarefa que requer aprovação humana.

    Após aprovar, o grafo continua a execução de onde parou.
    """
    if task_id not in _pending_threads:
        raise HTTPException(
            status_code=404,
            detail=f"Tarefa {task_id} não encontrada ou não requer aprovação",
        )

    thread_info = _pending_threads[task_id]
    thread_id = thread_info["thread_id"]

    if not request.approved:
        # Rejeição — marcar como falha
        _task_results[task_id] = {
            **_task_results.get(task_id, {}),
            "status": "failed",
            "final_response": f"Tarefa rejeitada: {request.reason or 'sem motivo informado'}",
        }
        del _pending_threads[task_id]
        return {"task_id": task_id, "status": "rejected", "message": "Tarefa rejeitada"}

    # Aprovação — continuar execução do grafo
    try:
        graph = _get_graph()
        config = {"configurable": {"thread_id": thread_id}}

        # Atualizar estado para prosseguir (approval_gate será executado)
        graph.update_state(
            config,
            {
                "requires_approval": False,
                "status": "executing",
            },
            as_node="approval_gate",
        )

        # Continuar execução
        final_state = None
        async for event in graph.astream(None, config=config):
            for node_name, node_output in event.items():
                logger.debug(f"  ► {node_name}: aprovação continuada")
                final_state = node_output

        # Obter estado final
        try:
            snapshot = graph.get_state(config)
            full_state = snapshot.values if snapshot else {}
        except Exception:
            full_state = final_state or {}

        result = {
            "task_id": task_id,
            "thread_id": thread_id,
            "status": full_state.get("status", "completed"),
            "final_response": full_state.get("final_response", ""),
            "action_results": full_state.get("action_results", []),
            "iterations": full_state.get("iteration", 0),
        }
        _task_results[task_id] = result
        del _pending_threads[task_id]

        return result

    except Exception as e:
        logger.error(f"Erro ao continuar tarefa aprovada: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def orchestrator_health() -> dict[str, Any]:
    """Health check do orquestrador."""
    from backend.orchestrator.nodes.act import _TOOL_REGISTRY

    return {
        "status": "ok",
        "engine": "langgraph",
        "registered_tools": sorted(_TOOL_REGISTRY.keys()),
        "tool_count": len(_TOOL_REGISTRY),
        "pending_approvals": len(_pending_threads),
        "completed_tasks": len(_task_results),
    }
