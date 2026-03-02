"""
SAGA Pattern Orchestrator - Distributed Transaction Management

Implementação de Saga Pattern para executar operações distribuídas com
suporte a compensação automática (rollback) em caso de falha.

Exemplo:
    saga = SagaOrchestrator()
    execution = saga.execute(
        saga_id="booking_123",
        steps=BOOKING_SAGA,
        context={"sale_id": "456", "email": "cliente@email.com"}
    )
    if execution.state == SagaState.FAILED:
        saga.compensate(saga_id)  # Reverte tudo automaticamente
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
import time

logger = logging.getLogger(__name__)


class SagaState(Enum):
    """Estados possíveis de um Saga durante execução."""

    PENDING = "pending"  # Aguardando execução
    IN_PROGRESS = "in_progress"  # Executando passos
    COMPENSATING = "compensating"  # Revertendo (fallback)
    SUCCEEDED = "succeeded"  # Completou com sucesso
    FAILED = "failed"  # Falhou e compensação completa
    PARTIALLY_COMPENSATED = "partially_compensated"  # Compensação parcial


@dataclass
class SagaStep:
    """Define um passo do Saga com ação e compensação."""

    name: str
    """Nome identificador do passo (ex: 'nf_api_call')"""

    action: Callable
    """Função a executar: action(context) -> Any"""

    compensation: Optional[Callable] = None
    """Função de compensação (rollback): compensation(context) -> None"""

    timeout: float = 30.0
    """Timeout em segundos"""

    retry_count: int = 3
    """Número de tentativas antes de falhar"""

    retry_delay: float = 1.0
    """Delay entre tentativas (segundos)"""

    idempotent: bool = True
    """Se True, permite reexecução segura"""

    def __post_init__(self):
        """Validação pós-inicialização."""
        if not callable(self.action):
            raise ValueError(
                f"SagaStep.action deve ser callable, recebeu {type(self.action)}"
            )

        if self.compensation is not None and not callable(self.compensation):
            raise ValueError(
                f"SagaStep.compensation deve ser callable, recebeu {type(self.compensation)}"
            )

        if self.timeout <= 0:
            raise ValueError(f"SagaStep.timeout deve ser > 0, recebeu {self.timeout}")

        if self.retry_count < 0:
            raise ValueError(
                f"SagaStep.retry_count deve ser >= 0, recebeu {self.retry_count}"
            )


@dataclass
class StepExecution:
    """Resultado da execução de um passo individual."""

    step_name: str
    status: str  # "pending", "running", "success", "failed"
    result: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    attempt: int = 0
    executed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    compensation_executed: bool = False


@dataclass
class SagaExecution:
    """Estado completo de um Saga em execução."""

    saga_id: str
    """Identificador único do saga"""

    saga_name: str
    """Nome descritivo do saga"""

    state: SagaState = SagaState.PENDING
    """Estado atual"""

    steps: List[SagaStep] = field(default_factory=list)
    """Lista de passos definidos"""

    step_executions: Dict[str, StepExecution] = field(default_factory=dict)
    """Histórico de execução de cada passo"""

    steps_completed: List[str] = field(default_factory=list)
    """Passos que completaram com sucesso"""

    failed_step: Optional[str] = None
    """Nome do passo que falhou (se houver)"""

    compensation_performed: bool = False
    """Se compensação já foi executada"""

    compensation_failed: bool = False
    """Se alguma compensação falhou"""

    created_at: datetime = field(default_factory=datetime.utcnow)
    """Timestamp de criação"""

    started_at: Optional[datetime] = None
    """Timestamp de início"""

    completed_at: Optional[datetime] = None
    """Timestamp de conclusão"""

    context: Dict[str, Any] = field(default_factory=dict)
    """Contexto compartilhado entre passos"""

    last_error: Optional[str] = None
    """Última mensagem de erro"""

    retry_count: int = 0
    """Número de reexecuções"""

    def duration(self) -> float:
        """Retorna duração total em segundos."""
        if self.started_at is None:
            return 0.0

        end = self.completed_at or datetime.now(timezone.utc)
        delta = end - self.started_at
        return delta.total_seconds()

    def success_rate(self) -> float:
        """Retorna % de passos completados."""
        if not self.steps:
            return 0.0
        return len(self.steps_completed) / len(self.steps)


class SagaOrchestrator:
    """Orquestrador central para execução de Sagas distribuídos."""

    def __init__(self, max_concurrent: int = 5, timeout_global: float = 300.0):
        """
        Inicializa o orquestrador.

        Args:
            max_concurrent: Máximo de sagas concorrentes
            timeout_global: Timeout global para qualquer saga (segundos)
        """
        self.logger = logging.getLogger(f"{__name__}.SagaOrchestrator")
        self.executions: Dict[str, SagaExecution] = {}
        self.max_concurrent = max_concurrent
        self.timeout_global = timeout_global
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)

        self.logger.info(f"SagaOrchestrator iniciado (max_concurrent={max_concurrent})")

    def define_saga(self, saga_name: str, steps: List[SagaStep]) -> None:
        """
        Define um novo saga reutilizável.

        Args:
            saga_name: Nome do saga (ex: "booking_saga")
            steps: Lista de SagaStep ordenados sequencialmente

        Raises:
            ValueError: Se steps está vazio ou duplicado
        """
        if not steps:
            raise ValueError("Saga deve ter pelo menos 1 passo")

        step_names = [s.name for s in steps]
        if len(step_names) != len(set(step_names)):
            raise ValueError("Nomes de passos duplicados detectados")

        self.logger.info(f"Saga '{saga_name}' definido com {len(steps)} passos")

    def execute(
        self,
        saga_id: str,
        saga_name: str,
        steps: List[SagaStep],
        context: Dict[str, Any],
    ) -> SagaExecution:
        """
        Executa um saga completo com todos os passos sequencialmente.

        Se um passo falhar após retries, executa compensação para todos os
        passos anteriores (na ordem reversa).

        Args:
            saga_id: ID único para rastrear (ex: "booking_123")
            saga_name: Nome descritivo (ex: "create_booking")
            steps: Lista de SagaStep a executar
            context: Dicionário compartilhado entre passos

        Returns:
            SagaExecution com estado final

        Example:
            execution = orchestrator.execute(
                saga_id="booking_123",
                saga_name="create_booking",
                steps=BOOKING_SAGA,
                context={"sale_id": "456", "email": "test@example.com"}
            )
            if execution.state == SagaState.SUCCEEDED:
                print("Booking criado com sucesso!")
            else:
                print(f"Falha: {execution.failed_step}")
        """
        # Validação
        if saga_id in self.executions:
            self.logger.warning(f"Saga {saga_id} já existe, retornando versão anterior")
            return self.executions[saga_id]

        if not steps:
            raise ValueError("Saga deve ter pelo menos 1 passo")

        # Inicializar execução
        execution = SagaExecution(
            saga_id=saga_id, saga_name=saga_name, steps=steps, context=context.copy()
        )
        self.executions[saga_id] = execution

        self.logger.info(
            f"Iniciando saga {saga_id} ({saga_name}) com {len(steps)} passos"
        )
        execution.state = SagaState.IN_PROGRESS
        execution.started_at = datetime.now(timezone.utc)

        try:
            # Executar cada passo sequencialmente
            for step in steps:
                success = self._execute_step(execution, step)

                if not success:
                    # Falha: executar compensação
                    execution.state = SagaState.COMPENSATING
                    execution.failed_step = step.name

                    self.logger.error(
                        f"Passo '{step.name}' falhou após {step.retry_count} tentativas. "
                        f"Iniciando compensação..."
                    )

                    self._compensate_saga(execution)
                    return execution

            # Sucesso!
            execution.state = SagaState.SUCCEEDED
            execution.completed_at = datetime.now(timezone.utc)

            self.logger.info(
                f"Saga {saga_id} completado com sucesso em {execution.duration():.2f}s"
            )

        except Exception as e:
            self.logger.error(f"Exceção inesperada no saga {saga_id}: {str(e)}")
            execution.state = SagaState.FAILED
            execution.last_error = str(e)
            execution.completed_at = datetime.now(timezone.utc)

        return execution

    def _execute_step(self, execution: SagaExecution, step: SagaStep) -> bool:
        """
        Executa um único passo com retry logic.

        Returns:
            True se sucesso, False se falha após todos os retries
        """
        step_exec = StepExecution(step_name=step.name, status="pending")
        execution.step_executions[step.name] = step_exec

        for attempt in range(step.retry_count + 1):
            step_exec.attempt = attempt
            step_exec.status = "running"

            try:
                self.logger.debug(
                    f"Executando passo '{step.name}' (tentativa {attempt + 1}/{step.retry_count + 1})"
                )

                start_time = time.time()
                result = step.action(execution.context)
                duration_ms = (time.time() - start_time) * 1000

                step_exec.result = result
                step_exec.status = "success"
                step_exec.duration_ms = duration_ms
                step_exec.executed_at = datetime.now(timezone.utc)

                execution.steps_completed.append(step.name)

                self.logger.debug(
                    f"Passo '{step.name}' completado em {duration_ms:.2f}ms"
                )

                return True

            except Exception as e:
                error_msg = str(e)
                step_exec.error = error_msg
                step_exec.error_type = type(e).__name__
                step_exec.status = "failed"

                self.logger.warning(
                    f"Passo '{step.name}' falhou (tentativa {attempt + 1}): {error_msg}"
                )

                if attempt < step.retry_count:
                    self.logger.debug(
                        f"Aguardando {step.retry_delay}s antes de retry..."
                    )
                    time.sleep(step.retry_delay)
                else:
                    execution.last_error = error_msg

        return False

    def _compensate_saga(self, execution: SagaExecution) -> None:
        """
        Executa compensações para todos os passos completados (ordem reversa).
        """
        completed_steps = [
            s for s in execution.steps if s.name in execution.steps_completed
        ]

        # Reverter na ordem inversa
        for step in reversed(completed_steps):
            if step.compensation is None:
                self.logger.debug(f"Passo '{step.name}' não tem compensação, pulando")
                continue

            try:
                self.logger.info(f"Executando compensação para '{step.name}'")

                start_time = time.time()
                step.compensation(execution.context)
                duration_ms = (time.time() - start_time) * 1000

                # Marcar compensação como executada
                if step.name in execution.step_executions:
                    execution.step_executions[step.name].compensation_executed = True

                self.logger.info(
                    f"Compensação '{step.name}' completada em {duration_ms:.2f}ms"
                )

            except Exception as e:
                self.logger.error(f"Compensação de '{step.name}' falhou: {str(e)}")
                execution.compensation_failed = True

        execution.compensation_performed = True
        execution.state = (
            SagaState.PARTIALLY_COMPENSATED
            if execution.compensation_failed
            else SagaState.FAILED
        )
        execution.completed_at = datetime.now(timezone.utc)

    def retry_failed(self, saga_id: str) -> SagaExecution:
        """
        Retenta um saga que falhou a partir do passo que falhou.

        Args:
            saga_id: ID do saga a retentar

        Returns:
            SagaExecution com novo estado

        Raises:
            ValueError: Se saga não existe ou não falhou
        """
        if saga_id not in self.executions:
            raise ValueError(f"Saga {saga_id} não encontrado")

        execution = self.executions[saga_id]

        if execution.state == SagaState.IN_PROGRESS:
            raise ValueError(f"Saga {saga_id} ainda está em progresso")

        if execution.state == SagaState.SUCCEEDED:
            self.logger.warning(f"Saga {saga_id} já completou com sucesso")
            return execution

        self.logger.info(
            f"Reexecutando saga {saga_id} a partir do passo '{execution.failed_step}'"
        )

        # Reset para reexecução
        execution.state = SagaState.IN_PROGRESS
        execution.retry_count += 1
        execution.started_at = datetime.now(timezone.utc)
        execution.completed_at = None

        # Remover o passo que falhou da lista de completados
        if execution.failed_step in execution.steps_completed:
            execution.steps_completed.remove(execution.failed_step)

        # Encontrar o índice do passo que falhou
        failed_index = None
        for i, step in enumerate(execution.steps):
            if step.name == execution.failed_step:
                failed_index = i
                break

        if failed_index is None:
            raise ValueError(f"Passo '{execution.failed_step}' não encontrado")

        # Executar a partir do passo que falhou
        for step in execution.steps[failed_index:]:
            success = self._execute_step(execution, step)

            if not success:
                execution.state = SagaState.COMPENSATING
                execution.failed_step = step.name

                self.logger.error(
                    f"Passo '{step.name}' falhou novamente, compensando..."
                )
                self._compensate_saga(execution)
                return execution

        execution.state = SagaState.SUCCEEDED
        execution.completed_at = datetime.now(timezone.utc)

        self.logger.info(f"Saga {saga_id} reexecutado com sucesso")

        return execution

    def get_status(self, saga_id: str) -> Optional[SagaExecution]:
        """
        Retorna status atual de um saga.

        Args:
            saga_id: ID do saga

        Returns:
            SagaExecution se encontrado, None caso contrário
        """
        return self.executions.get(saga_id)

    def list_executions(self, state: Optional[SagaState] = None) -> List[SagaExecution]:
        """
        Lista todas as execuções, opcionalmente filtradas por estado.

        Args:
            state: SagaState para filtrar (None = todos)

        Returns:
            Lista de SagaExecution
        """
        executions = list(self.executions.values())

        if state:
            executions = [e for e in executions if e.state == state]

        # Ordenar por timestamp descending
        executions.sort(key=lambda e: e.created_at, reverse=True)

        return executions

    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas gerais do orquestrador.

        Returns:
            Dict com métricas
        """
        all_executions = list(self.executions.values())

        succeeded = len([e for e in all_executions if e.state == SagaState.SUCCEEDED])
        failed = len([e for e in all_executions if e.state == SagaState.FAILED])
        in_progress = len(
            [e for e in all_executions if e.state == SagaState.IN_PROGRESS]
        )

        avg_duration = 0.0
        if succeeded > 0:
            total_duration = sum(
                e.duration() for e in all_executions if e.state == SagaState.SUCCEEDED
            )
            avg_duration = total_duration / succeeded

        return {
            "total_executions": len(all_executions),
            "succeeded": succeeded,
            "failed": failed,
            "in_progress": in_progress,
            "success_rate": succeeded / len(all_executions) if all_executions else 0.0,
            "avg_duration_seconds": avg_duration,
            "total_retries": sum(e.retry_count for e in all_executions),
        }

    def print_stats(self) -> str:
        """Retorna estatísticas formatadas como string."""
        stats = self.get_stats()

        lines = [
            "=" * 70,
            "SAGA ORCHESTRATOR STATISTICS",
            "=" * 70,
            f"Total Executions: {stats['total_executions']}",
            f"  ✓ Succeeded: {stats['succeeded']}",
            f"  ✗ Failed: {stats['failed']}",
            f"  ⟳ In Progress: {stats['in_progress']}",
            f"Success Rate: {stats['success_rate']:.1%}",
            f"Avg Duration: {stats['avg_duration_seconds']:.2f}s",
            f"Total Retries: {stats['total_retries']}",
            "=" * 70,
        ]

        return "\n".join(lines)

    def cleanup(self) -> None:
        """Limpa recursos (executor, etc)."""
        self.executor.shutdown(wait=True)
        self.logger.info("SagaOrchestrator finalizado")


# Factory para uso global
_saga_orchestrator: Optional[SagaOrchestrator] = None


def get_saga_orchestrator() -> SagaOrchestrator:
    """
    Retorna instância global do SagaOrchestrator (singleton).

    Returns:
        SagaOrchestrator singleton
    """
    global _saga_orchestrator

    if _saga_orchestrator is None:
        _saga_orchestrator = SagaOrchestrator()

    return _saga_orchestrator


def reset_saga_orchestrator() -> None:
    """Reseta a instância global (útil para testes)."""
    global _saga_orchestrator

    if _saga_orchestrator is not None:
        _saga_orchestrator.cleanup()

    _saga_orchestrator = None
