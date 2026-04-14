"""
NEXUS Orchestrator — LangGraph State Machine
=============================================
Orquestrador de agentes baseado em LangGraph com:
- Estado tipado e persistente
- Loop sense → plan → policy → act → check
- Action firewall com políticas declarativas
- Human-in-the-loop para ações críticas
- Tools tipadas para browser, CRM e integrações
"""
from orchestrator.graph import create_orchestrator_graph, run_task
from orchestrator.state import AgentState, TaskStatus

__all__ = [
    "create_orchestrator_graph",
    "run_task",
    "AgentState",
    "TaskStatus",
]
