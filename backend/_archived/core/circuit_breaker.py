"""Circuit Breaker Pattern for API Resilience and Fault Tolerance.

Implementação do padrão Circuit Breaker com 3 estados:
1. CLOSED: Normal operation, requests pass through
2. OPEN: Failure threshold exceeded, requests fail fast
3. HALF_OPEN: Testing recovery, limited requests allowed

Usado para:
- Proteger APIs externas (Gmail, WhatsApp, Telegram, Email)
- Evitar cascata de falhas em sistema distribuído
- Implementar fallback automático
- Recuperação com backoff exponencial

Inspiração: Netflix Hystrix, AWS Lambda Circuit Breakers
Complexidade: O(1) per request (apenas counter checks)
"""

from __future__ import annotations

import logging
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Estados do Circuit Breaker."""

    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Failing, reject requests
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuração do Circuit Breaker.

    Attributes:
        failure_threshold: Número de falhas consecutivas para abrir (padrão: 5)
        success_threshold: Número de sucessos em HALF_OPEN para fechar (padrão: 2)
        timeout: Segundos em OPEN antes de tentar HALF_OPEN (padrão: 60)
        name: Nome identificador para logging
    """

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: int = 60
    name: str = "CircuitBreaker"


@dataclass
class CircuitBreakerStats:
    """Estatísticas do Circuit Breaker."""

    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_rejections: int = 0  # Requests rejected in OPEN state
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    state_changes: int = 0
    last_state_change: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    last_failure_reason: Optional[str] = None

    def success_rate(self) -> float:
        """Calcula taxa de sucesso (0-100%)."""
        if self.total_requests == 0:
            return 0.0
        return (self.total_successes / self.total_requests) * 100

    def failure_rate(self) -> float:
        """Calcula taxa de falha (0-100%)."""
        return 100.0 - self.success_rate()


class CircuitBreaker:
    """Circuit Breaker para proteger chamadas a APIs externas.

    States:
        CLOSED: Normal, requests pass through
        OPEN: Failures exceeded, requests fail fast
        HALF_OPEN: Limited requests to test recovery

    Exemplo:
        >>> cb = CircuitBreaker(
        ...     name="gmail_api",
        ...     failure_threshold=5,
        ...     success_threshold=2,
        ...     timeout=60
        ... )
        >>>
        >>> @cb.guard()
        ... def send_email(to, subject, body):
        ...     # Implementação...
        ...     return {"status": "success"}
        >>>
        >>> # Chamada automática com proteção de circuit breaker
        >>> result = send_email("user@example.com", "Test", "Body")
        >>> if result:  # Se circuit está OPEN, retorna None
        ...     print(f"Email enviado: {result}")
    """

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        """Inicializa Circuit Breaker.

        Args:
            config: Configuração do breaker (padrão: default config)
        """
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._last_failure_time: Optional[datetime] = None

        logger.info(
            "CircuitBreaker '%s' inicializado | "
            "failure_threshold=%d, success_threshold=%d, timeout=%ds",
            self.config.name,
            self.config.failure_threshold,
            self.config.success_threshold,
            self.config.timeout,
        )

    def _can_attempt_reset(self) -> bool:
        """Verifica se pode tentar reset (mudar para HALF_OPEN).

        Retorna True se:
        - Estado é OPEN
        - Tempo de timeout expirou desde última falha
        """
        if self.state != CircuitState.OPEN:
            return False

        if self._last_failure_time is None:
            return True

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.config.timeout

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transiciona para novo estado com logging."""
        old_state = self.state
        self.state = new_state
        self.stats.state_changes += 1
        self.stats.last_state_change = datetime.now()

        logger.warning(
            "CircuitBreaker '%s' transição: %s -> %s",
            self.config.name,
            old_state.value,
            new_state.value,
        )

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Executa função com proteção de circuit breaker.

        Args:
            func: Função a executar
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados

        Returns:
            Resultado da função ou None se circuit está OPEN

        Raises:
            Propaga exceções de func se circuit está CLOSED/HALF_OPEN
        """
        self.stats.total_requests += 1

        # Se está OPEN e pode tentar reset, vai para HALF_OPEN
        if self._can_attempt_reset():
            self._transition_to(CircuitState.HALF_OPEN)
            logger.info("CircuitBreaker '%s' tentando recuperação", self.config.name)

        # Se está OPEN (e não pode tentar reset), fail fast
        if self.state == CircuitState.OPEN:
            self.stats.total_rejections += 1
            logger.warning(
                "CircuitBreaker '%s' OPEN — rejeitando requisição (%d rejections)",
                self.config.name,
                self.stats.total_rejections,
            )
            return None

        # Executa em CLOSED ou HALF_OPEN
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(str(e))
            raise

    def _on_success(self) -> None:
        """Callback após sucesso."""
        self.stats.total_successes += 1
        self.stats.consecutive_successes += 1
        self.stats.consecutive_failures = 0

        # Em HALF_OPEN: se atingiu threshold de sucessos, fecha
        if self.state == CircuitState.HALF_OPEN:
            if self.stats.consecutive_successes >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
                logger.info(
                    "CircuitBreaker '%s' RECUPERADO (CLOSED)",
                    self.config.name,
                )

    def _on_failure(self, reason: str) -> None:
        """Callback após falha."""
        self.stats.total_failures += 1
        self.stats.consecutive_failures += 1
        self.stats.consecutive_successes = 0
        self.stats.last_failure_time = datetime.now()
        self.stats.last_failure_reason = reason
        self._last_failure_time = datetime.now()

        # Se atingiu threshold de falhas em CLOSED/HALF_OPEN, abre
        if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
            if self.stats.consecutive_failures >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                logger.error(
                    "CircuitBreaker '%s' ABERTO após %d falhas | Motivo: %s",
                    self.config.name,
                    self.config.failure_threshold,
                    reason,
                )

    def guard(self) -> Callable:
        """Decorator para proteger função com circuit breaker.

        Uso:
            @circuit_breaker.guard()
            def minha_funcao():
                pass

        Returns:
            Decorator function
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return self.call(func, *args, **kwargs)

            return wrapper

        return decorator

    def get_stats(self) -> dict:
        """Retorna estatísticas do circuit breaker.

        Returns:
            Dict com métricas (total_requests, success_rate, state, etc)
        """
        return {
            "name": self.config.name,
            "state": self.state.value,
            "total_requests": self.stats.total_requests,
            "total_successes": self.stats.total_successes,
            "total_failures": self.stats.total_failures,
            "total_rejections": self.stats.total_rejections,
            "success_rate": f"{self.stats.success_rate():.1f}%",
            "failure_rate": f"{self.stats.failure_rate():.1f}%",
            "consecutive_failures": self.stats.consecutive_failures,
            "consecutive_successes": self.stats.consecutive_successes,
            "state_changes": self.stats.state_changes,
            "last_state_change": self.stats.last_state_change.isoformat()
            if self.stats.last_state_change
            else None,
            "last_failure_reason": self.stats.last_failure_reason,
        }

    def print_stats(self) -> str:
        """Retorna string formatada com estatísticas."""
        stats = self.get_stats()
        lines = [
            f"\n=== CIRCUIT BREAKER STATS: {stats['name']} ===",
            f"State: {stats['state']}",
            f"Total Requests: {stats['total_requests']}",
            f"  Successes: {stats['total_successes']}",
            f"  Failures: {stats['total_failures']}",
            f"  Rejections (OPEN state): {stats['total_rejections']}",
            f"Success Rate: {stats['success_rate']}",
            f"Consecutive Failures: {stats['consecutive_failures']}/{self.config.failure_threshold}",
            f"Consecutive Successes: {stats['consecutive_successes']}/{self.config.success_threshold}",
            f"State Changes: {stats['state_changes']}",
            f"Last State Change: {stats['last_state_change']}",
            f"Last Failure: {stats['last_failure_reason']}",
        ]
        return "\n".join(lines)

    def reset(self) -> None:
        """Reset circuit breaker para estado CLOSED com stats zeradas."""
        self._transition_to(CircuitState.CLOSED)
        self.stats = CircuitBreakerStats()
        logger.info("CircuitBreaker '%s' resetado", self.config.name)

    def force_open(self) -> None:
        """Force circuit breaker para estado OPEN (útil para testes/manutenção)."""
        self._transition_to(CircuitState.OPEN)
        logger.warning("CircuitBreaker '%s' forçado para OPEN", self.config.name)

    def force_closed(self) -> None:
        """Force circuit breaker para estado CLOSED."""
        self._transition_to(CircuitState.CLOSED)
        logger.warning("CircuitBreaker '%s' forçado para CLOSED", self.config.name)
