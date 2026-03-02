"""
Fila de Prioridade para Orquestração de Agentes.

Implementação de Min-Heap (usando heapq) para garantir que agentes críticos
(ex: Prazos DAS vencendo amanhã) sejam executados antes de tarefas triviais.

FUNDAMENTO TEÓRICO:
- Disciplina CS: Estruturas de Dados (Heaps)
- Complexidade: O(log n) para inserção/remoção, O(1) para min
- Trade-off: Memória O(n), construção O(n log n)
- Alternativas: Red-Black Tree O(log n), mas Heap é mais simples

QUANDO USAR:
✅ Centenas de tarefas concorrentes
✅ Tarefas com deadlines críticos
✅ Necessidade de resposta previsível
✅ Escala até 10k+ agentes simultâneos

QUANDO NÃO USAR:
❌ < 10 tarefas (overhead não justificado)
❌ Todas tarefas têm mesma prioridade
❌ Processamento em lote (ordenação simples suficiente)
"""

import heapq
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict
from enum import IntEnum
import logging

logger = logging.getLogger("agent_queue")


class TaskPriority(IntEnum):
    """Níveis de prioridade (menor valor = maior urgência)."""

    CRITICAL = 1  # Prazo vence hoje, erro em produção
    HIGH = 2  # Prazo vence em 1-2 dias, cliente esperando
    MEDIUM = 3  # Prazo em 3-7 dias, operacional normal
    LOW = 4  # Prazo > 7 dias, background jobs
    DEFERRED = 5  # Pode esperar indefinidamente (análise futura)


@dataclass(order=True)
class AgentTask:
    """Tarefa de agente para fila de prioridade.

    Atributos:
        priority (int): Nível de prioridade (TaskPriority enum)
        deadline (float): Timestamp Unix do vencimento
        cost (int): Custo estimado em pontos (API calls, tempo em ms)
        task_id (str): ID único da tarefa (auto-gerado)
        agent_name (str): Nome do agente executando (ex: "deadlines_agent")
        client_id (str): ID do cliente associado
        payload (dict): Dados da tarefa (não afeta ordenação)
        created_at (float): Timestamp de criação (para tiebreaker)

    Ordem de comparação (tiebreaker):
    1. priority (menor = mais urgente)
    2. deadline (mais próximo = mais urgente)
    3. cost (menor custo = mais eficiente rodar antes)
    4. created_at (FIFO para mesma prioridade/deadline/cost)
    """

    priority: int
    deadline: float
    cost: int
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_name: str = field(default="unknown_agent")
    client_id: str = field(default="unknown_client")
    payload: Dict[str, Any] = field(default_factory=dict, compare=False)
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())

    def __repr__(self) -> str:
        """Representação legível."""
        priority_name = TaskPriority(self.priority).name
        deadline_str = datetime.fromtimestamp(self.deadline).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return (
            f"AgentTask({self.task_id}, {priority_name}, "
            f"deadline={deadline_str}, cost={self.cost}, "
            f"agent={self.agent_name}, client={self.client_id})"
        )

    def seconds_until_deadline(self) -> float:
        """Calcula segundos restantes até o deadline."""
        return self.deadline - datetime.now().timestamp()

    def is_overdue(self) -> bool:
        """Verifica se a tarefa já venceu."""
        return self.seconds_until_deadline() < 0


class AgentQueue:
    """Fila de prioridade para agentes com operações O(log n).

    Exemplo de uso:
        queue = AgentQueue()

        # Tarefa crítica: DAS vence amanhã
        queue.push(
            priority=TaskPriority.CRITICAL,
            deadline=datetime.now() + timedelta(days=1),
            cost=2,  # 2 API calls
            agent_name="deadlines_agent",
            client_id="client_123",
            payload={"obligation": "DAS", "valor": 150.00}
        )

        # Tarefa normal: agendamento
        queue.push(
            priority=TaskPriority.MEDIUM,
            deadline=datetime.now() + timedelta(days=7),
            cost=5,  # 5 API calls (WhatsApp)
            agent_name="attendance_agent",
            client_id="client_456",
            payload={"cliente": "João", "horario": "14:00"}
        )

        # Executar tarefas em ordem
        while queue.size() > 0:
            task = queue.pop()
            resultado = executar_agente(task)
            if not resultado['sucesso']:
                # Reinsert com penalty de prioridade
                queue.push_task(task)  # re-push na heap
    """

    def __init__(self, max_size: Optional[int] = None):
        """Inicializa a fila.

        Args:
            max_size: Limite máximo de tarefas (None = ilimitado).
                     Útil para evitar memory leaks em ambientes com
                     produção de tarefas muito rápida.
        """
        self._heap: List[AgentTask] = []
        self.max_size = max_size
        self.stats = {
            "total_pushed": 0,
            "total_popped": 0,
            "total_rejected": 0,  # Rejeitadas por max_size
        }

    def push(
        self,
        priority: int,
        deadline: datetime,
        cost: int,
        agent_name: str,
        client_id: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> Optional[str]:
        """Insere tarefa na fila (O(log n)).

        Args:
            priority: Nível TaskPriority
            deadline: datetime do vencimento
            cost: Custo estimado (pontos)
            agent_name: Nome do agente
            client_id: ID do cliente
            payload: Dados da tarefa
            task_id: ID único (auto-gerado se None)

        Returns:
            task_id da tarefa inserida, ou None se rejeitada por max_size

        Raises:
            ValueError: Se priority, cost ou deadline inválidos
        """
        # Validações
        if not isinstance(priority, int) or priority < 1 or priority > 5:
            raise ValueError(f"Priority inválida: {priority} (deve ser 1-5)")

        if cost < 0:
            raise ValueError(f"Cost não pode ser negativo: {cost}")

        if not isinstance(deadline, datetime):
            raise ValueError(f"Deadline deve ser datetime, recebido {type(deadline)}")

        # Verificar limite máximo
        if self.max_size and self.size() >= self.max_size:
            logger.warning(
                f"Fila cheia ({self.size()}/{self.max_size}). "
                f"Rejeitando tarefa {agent_name}/{client_id}"
            )
            self.stats["total_rejected"] += 1
            return None

        # Criar e inserir tarefa
        deadline_ts = deadline.timestamp()
        task = AgentTask(
            priority=priority,
            deadline=deadline_ts,
            cost=cost,
            task_id=task_id or str(uuid.uuid4())[:8],
            agent_name=agent_name,
            client_id=client_id,
            payload=payload,
        )

        heapq.heappush(self._heap, task)
        self.stats["total_pushed"] += 1

        logger.debug(f"[PUSH] {task}")
        return task.task_id

    def push_task(self, task: AgentTask) -> None:
        """Insere AgentTask pré-construída (útil para retry).

        Args:
            task: AgentTask a inserir
        """
        heapq.heappush(self._heap, task)
        self.stats["total_pushed"] += 1
        logger.debug(f"[PUSH_TASK] {task}")

    def pop(self) -> Optional[AgentTask]:
        """Remove e retorna tarefa de maior prioridade (O(log n)).

        Returns:
            Próxima AgentTask com maior prioridade, ou None se vazio
        """
        if not self._heap:
            logger.debug("[POP] Fila vazia")
            return None

        task = heapq.heappop(self._heap)
        self.stats["total_popped"] += 1

        if task.is_overdue():
            logger.warning(f"[POP] Tarefa vencida: {task}")

        logger.debug(f"[POP] {task}")
        return task

    def peek(self) -> Optional[AgentTask]:
        """Retorna próxima tarefa SEM remover (O(1)).

        Útil para inspecionar antes de processar, ou para métricas.

        Returns:
            Próxima AgentTask, ou None se vazio
        """
        return self._heap[0] if self._heap else None

    def size(self) -> int:
        """Retorna número de tarefas na fila (O(1))."""
        return len(self._heap)

    def is_empty(self) -> bool:
        """Verifica se a fila está vazia (O(1))."""
        return len(self._heap) == 0

    def clear(self) -> None:
        """Limpa a fila (O(1))."""
        self._heap.clear()
        logger.info("[CLEAR] Fila esvaziada")

    def get_all_tasks(self) -> List[AgentTask]:
        """Retorna todas as tarefas em ordem de prioridade.

        CUIDADO: Esta operação é O(n log n) (reconstrói a heap).
        Use com moderação (ex: apenas para debugging/logging).

        Returns:
            List de tarefas ordenadas por prioridade
        """
        # Cópia para não modificar a heap original
        heap_copy = self._heap.copy()
        sorted_tasks = []

        while heap_copy:
            sorted_tasks.append(heapq.heappop(heap_copy))

        return sorted_tasks

    def get_tasks_for_agent(self, agent_name: str) -> List[AgentTask]:
        """Retorna todas as tarefas de um agente específico (O(n)).

        Args:
            agent_name: Nome do agente (ex: "deadlines_agent")

        Returns:
            List de AgentTasks para esse agente
        """
        return [t for t in self._heap if t.agent_name == agent_name]

    def get_tasks_for_client(self, client_id: str) -> List[AgentTask]:
        """Retorna todas as tarefas de um cliente (O(n)).

        Args:
            client_id: ID do cliente

        Returns:
            List de AgentTasks para esse cliente
        """
        return [t for t in self._heap if t.client_id == client_id]

    def remove_task(self, task_id: str) -> bool:
        """Remove tarefa específica por ID (O(n)).

        CUIDADO: Esta operação é O(n) porque precisa encontrar a tarefa
        antes de remover. Use apenas quando absolutamente necessário.

        Args:
            task_id: ID da tarefa a remover

        Returns:
            True se removida, False se não encontrada
        """
        for i, task in enumerate(self._heap):
            if task.task_id == task_id:
                # Trocar com último elemento e heappop
                self._heap[i] = self._heap[-1]
                self._heap.pop()

                # Reheapify (pode descer ou subir a posição)
                if i < len(self._heap):
                    heapq.heapify(self._heap)

                logger.info(f"[REMOVE] Tarefa {task_id} removida")
                return True

        logger.warning(f"[REMOVE] Tarefa {task_id} não encontrada")
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso da fila.

        Returns:
            Dict com total_pushed, total_popped, total_rejected, size_atual
        """
        return {
            **self.stats,
            "size_atual": self.size(),
            "max_size": self.max_size,
        }

    def print_stats(self) -> str:
        """Retorna string formatada com estatísticas."""
        stats = self.get_stats()
        return (
            f"=== AGENT QUEUE STATS ===\n"
            f"Total Pushed: {stats['total_pushed']}\n"
            f"Total Popped: {stats['total_popped']}\n"
            f"Total Rejected: {stats['total_rejected']}\n"
            f"Current Size: {stats['size_atual']}/{stats['max_size'] or '∞'}\n"
            f"Efficiency (popped/pushed): {stats['total_popped'] / max(1, stats['total_pushed']) * 100:.1f}%"
        )


# ============================================================================
# HELPERS & UTILITIES
# ============================================================================


def create_deadline(days_ahead: int, hours: int = 0, minutes: int = 0) -> datetime:
    """Cria deadline relativo (dias a partir de agora).

    Exemplo:
        deadline = create_deadline(days_ahead=1, hours=9)  # Amanhã 9h

    Args:
        days_ahead: Dias no futuro
        hours: Horas adicionais
        minutes: Minutos adicionais

    Returns:
        datetime do deadline
    """
    return datetime.now() + timedelta(days=days_ahead, hours=hours, minutes=minutes)


def create_critical_deadline(hours: int = 24) -> datetime:
    """Cria deadline crítico (padrão: próximas 24h).

    Args:
        hours: Horas até deadline

    Returns:
        datetime do deadline
    """
    return datetime.now() + timedelta(hours=hours)
