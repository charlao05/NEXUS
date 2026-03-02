"""
Estado tipado do orquestrador LangGraph.
Segue o padrão TypedDict para que o LangGraph rastreie
mudanças incrementais e permita checkpointing.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from langgraph.graph import add_messages
from pydantic import BaseModel, Field
from typing_extensions import Annotated, TypedDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING = "pending"
    SENSING = "sensing"
    PLANNING = "planning"
    VALIDATING = "validating"
    EXECUTING = "executing"
    CHECKING = "checking"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionRisk(str, Enum):
    LOW = "low"           # Leitura, consulta
    MEDIUM = "medium"     # Escrita em sistema interno
    HIGH = "high"         # Email externo, pagamento, exclusão
    CRITICAL = "critical" # Ação irreversível, requer aprovação humana


# ---------------------------------------------------------------------------
# Modelos Pydantic para ações planejadas
# ---------------------------------------------------------------------------

class PlannedAction(BaseModel):
    """Uma ação proposta pelo LLM planner."""
    tool: str = Field(description="Nome da tool a executar")
    params: dict[str, Any] = Field(default_factory=dict, description="Parâmetros da tool")
    reason: str = Field(default="", description="Justificativa do planner")
    risk: ActionRisk = Field(default=ActionRisk.LOW, description="Nível de risco avaliado")


class ActionResult(BaseModel):
    """Resultado da execução de uma ação."""
    tool: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: int = 0


class PolicyDecision(BaseModel):
    """Decisão do firewall de políticas."""
    action: PlannedAction
    allowed: bool
    reason: str = ""
    modified_params: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Estado principal do grafo (TypedDict para LangGraph)
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    """Estado compartilhado entre todos os nós do grafo.
    
    O LangGraph rastreia mudanças campo a campo e permite
    persistência via checkpointer (SQLite, Postgres, Redis).
    """
    # --- Identidade da tarefa ---
    task_id: str
    agent_type: str                     # clientes, financeiro, assistente, browser, nf
    user_id: int
    
    # --- Objetivo ---
    goal: str                           # O que o usuário quer
    original_message: str               # Mensagem original do usuário
    
    # --- Contexto ---
    crm_context: str                    # Dados do CRM formatados
    page_observation: str               # DOM/screenshot resumido (browser agent)
    site_config: dict[str, Any]         # Config do site (de config/sites.yaml)
    
    # --- Histórico de conversa (append-only via add_messages) ---
    messages: Annotated[list, add_messages]
    
    # --- Plano ---
    planned_actions: list[dict]         # Lista de PlannedAction.model_dump()
    current_step: int                   # Índice da ação sendo executada
    max_steps: int                      # Limite de steps para evitar loops infinitos
    
    # --- Política ---
    policy_decisions: list[dict]        # Lista de PolicyDecision.model_dump()
    requires_approval: bool             # Se precisa aprovação humana
    approval_message: str               # Mensagem para o humano aprovar
    
    # --- Resultados ---
    action_results: list[dict]          # Lista de ActionResult.model_dump()
    final_response: str                 # Resposta final pro usuário
    
    # --- Controle ---
    status: str                         # TaskStatus value
    iteration: int                      # Contador de iterações do loop
    max_iterations: int                 # Limite de iterações (anti-loop)
    error: str | None                   # Último erro
    
    # --- Metadata ---
    created_at: str                     # ISO timestamp
    updated_at: str                     # ISO timestamp


# ---------------------------------------------------------------------------
# Helpers para criar estado inicial
# ---------------------------------------------------------------------------

def create_initial_state(
    *,
    task_id: str,
    agent_type: str,
    user_id: int,
    goal: str,
    original_message: str = "",
    max_iterations: int = 10,
    max_steps: int = 20,
    site_config: dict[str, Any] | None = None,
) -> AgentState:
    """Cria estado inicial para uma nova tarefa."""
    now = datetime.now().isoformat()
    return AgentState(
        task_id=task_id,
        agent_type=agent_type,
        user_id=user_id,
        goal=goal,
        original_message=original_message or goal,
        crm_context="",
        page_observation="",
        site_config=site_config or {},
        messages=[],
        planned_actions=[],
        current_step=0,
        max_steps=max_steps,
        policy_decisions=[],
        requires_approval=False,
        approval_message="",
        action_results=[],
        final_response="",
        status=TaskStatus.PENDING.value,
        iteration=0,
        max_iterations=max_iterations,
        error=None,
        created_at=now,
        updated_at=now,
    )
