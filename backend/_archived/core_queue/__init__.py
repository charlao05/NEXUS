"""Core infrastructure for Codex Operator.

Módulo com componentes fundamentais da arquitetura, incluindo:
- Priority Queue (Min-Heap) para orquestração eficiente de tarefas
- Circuit Breaker para confiabilidade distribuída
- Event sourcing para auditoria e compliance
"""

from backend.core.agent_queue import (
    AgentQueue,
    AgentTask,
    TaskPriority,
    create_deadline,
    create_critical_deadline,
)
from backend.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerStats,
    CircuitState,
)

__all__ = [
    "AgentQueue",
    "AgentTask",
    "TaskPriority",
    "create_deadline",
    "create_critical_deadline",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerStats",
    "CircuitState",
]
