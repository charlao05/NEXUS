"""
DomainCircuitBreaker — Quebra circuito por dominio.
=====================================================
Protege contra falhas em cascata quando sites externos (Receita,
gov.br, prefeituras) ficam fora do ar ou bloqueiam o IP.

Estados:
- CLOSED   — operacao normal, falhas sao contadas
- OPEN     — bloqueia chamadas por X segundos apos atingir threshold
- HALF_OPEN — apos timeout, permite uma chamada de teste; se sucesso, fecha

Backend:
- Redis (preferencial) — estado distribuido entre instancias
- In-memory fallback — quando Redis indisponivel

Configuracao via env:
- CIRCUIT_FAILURE_THRESHOLD (default 5) — falhas antes de abrir
- CIRCUIT_RECOVERY_TIMEOUT  (default 300) — segundos em OPEN antes de tentar HALF_OPEN
- CIRCUIT_SUCCESS_THRESHOLD (default 2) — sucessos consecutivos para fechar de HALF_OPEN
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", "5"))
RECOVERY_TIMEOUT = int(os.getenv("CIRCUIT_RECOVERY_TIMEOUT", "300"))
SUCCESS_THRESHOLD = int(os.getenv("CIRCUIT_SUCCESS_THRESHOLD", "2"))
KEY_PREFIX = "nexus:browser:circuit"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitInfo:
    domain: str
    state: str = CircuitState.CLOSED.value
    failures: int = 0
    successes: int = 0  # contador para HALF_OPEN -> CLOSED
    opened_at: float = 0.0
    last_failure_at: float = 0.0
    last_success_at: float = 0.0


class CircuitOpenError(Exception):
    """Levantado quando o circuito esta aberto e a chamada eh rejeitada."""

    def __init__(self, domain: str, retry_in_seconds: int):
        self.domain = domain
        self.retry_in_seconds = retry_in_seconds
        super().__init__(
            f"Circuit OPEN para '{domain}' — site indisponivel ou bloqueado. "
            f"Tente novamente em {retry_in_seconds}s."
        )


# ---------------------------------------------------------------------------
# DomainCircuitBreaker
# ---------------------------------------------------------------------------

class DomainCircuitBreaker:
    """Circuit breaker por dominio.

    Singleton thread-safe via get_instance().
    """

    _instance: Optional[DomainCircuitBreaker] = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        failure_threshold: int = FAILURE_THRESHOLD,
        recovery_timeout: int = RECOVERY_TIMEOUT,
        success_threshold: int = SUCCESS_THRESHOLD,
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._success_threshold = success_threshold
        self._memory: dict[str, CircuitInfo] = {}
        self._memory_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> DomainCircuitBreaker:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._instance_lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Backend
    # ------------------------------------------------------------------

    def _get_redis(self):
        try:
            from app.api.redis_client import get_redis
            return get_redis()
        except Exception:
            return None

    def _build_key(self, domain: str) -> str:
        return f"{KEY_PREFIX}:{domain.lower()}"

    def _load(self, domain: str) -> CircuitInfo:
        """Carrega estado do circuito (Redis -> memoria)."""
        key = self._build_key(domain)

        redis = self._get_redis()
        if redis is not None:
            try:
                raw = redis.get(key)
                if raw:
                    data = json.loads(raw)
                    return CircuitInfo(**data)
            except Exception as e:
                logger.debug(f"Circuit Redis load falhou: {e}")

        with self._memory_lock:
            return self._memory.get(domain) or CircuitInfo(domain=domain)

    def _store(self, info: CircuitInfo) -> None:
        """Persiste estado do circuito."""
        key = self._build_key(info.domain)

        redis = self._get_redis()
        if redis is not None:
            try:
                # TTL = 2x recovery_timeout, garante que estado nao fica para sempre
                redis.setex(key, self._recovery_timeout * 2, json.dumps(asdict(info)))
                return
            except Exception as e:
                logger.debug(f"Circuit Redis store falhou: {e}")

        with self._memory_lock:
            self._memory[info.domain] = info

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def check(self, url_or_domain: str) -> None:
        """Verifica se a chamada pode prosseguir. Levanta CircuitOpenError se aberto.

        Se o circuito esta OPEN ha mais de recovery_timeout, transiciona para HALF_OPEN
        e permite UMA chamada de teste.
        """
        domain = _normalize_domain(url_or_domain)
        info = self._load(domain)

        # Estado CLOSED — sempre permite
        if info.state == CircuitState.CLOSED.value:
            return

        # Estado OPEN — checa se passou recovery timeout
        if info.state == CircuitState.OPEN.value:
            elapsed = time.time() - info.opened_at
            if elapsed >= self._recovery_timeout:
                # Transicao para HALF_OPEN
                info.state = CircuitState.HALF_OPEN.value
                info.successes = 0
                self._store(info)
                logger.info(
                    f"Circuit transition OPEN -> HALF_OPEN | domain={domain} "
                    f"after={int(elapsed)}s"
                )
                return  # Permite a chamada de teste
            else:
                retry_in = int(self._recovery_timeout - elapsed)
                raise CircuitOpenError(domain, retry_in)

        # Estado HALF_OPEN — permite (mas registra resultado)
        return

    def record_success(self, url_or_domain: str) -> None:
        """Registra sucesso. Se em HALF_OPEN, acelera para CLOSED."""
        domain = _normalize_domain(url_or_domain)
        info = self._load(domain)

        info.last_success_at = time.time()

        if info.state == CircuitState.CLOSED.value:
            # Reset contador de falhas em sucesso
            if info.failures > 0:
                info.failures = 0
                self._store(info)
            return

        if info.state == CircuitState.HALF_OPEN.value:
            info.successes += 1
            if info.successes >= self._success_threshold:
                # Fecha o circuito
                info.state = CircuitState.CLOSED.value
                info.failures = 0
                info.successes = 0
                info.opened_at = 0.0
                logger.info(f"Circuit CLOSED (recovery) | domain={domain}")
            self._store(info)
            return

        # Em OPEN, nao deveria acontecer mas reseta sucessos
        info.successes = 0
        self._store(info)

    def record_failure(self, url_or_domain: str) -> None:
        """Registra falha. Abre o circuito se threshold for atingido."""
        domain = _normalize_domain(url_or_domain)
        info = self._load(domain)

        info.last_failure_at = time.time()
        info.failures += 1

        # Em HALF_OPEN, qualquer falha re-abre
        if info.state == CircuitState.HALF_OPEN.value:
            info.state = CircuitState.OPEN.value
            info.opened_at = time.time()
            info.successes = 0
            logger.warning(
                f"Circuit re-OPEN (HALF_OPEN failure) | domain={domain}"
            )
            self._store(info)
            return

        # Em CLOSED, abre apos threshold
        if info.state == CircuitState.CLOSED.value:
            if info.failures >= self._failure_threshold:
                info.state = CircuitState.OPEN.value
                info.opened_at = time.time()
                logger.warning(
                    f"Circuit OPEN | domain={domain} failures={info.failures} "
                    f"threshold={self._failure_threshold}"
                )

        self._store(info)

    def is_open(self, url_or_domain: str) -> bool:
        """Retorna True se o circuito esta aberto e nao pode receber chamadas."""
        try:
            self.check(url_or_domain)
            return False
        except CircuitOpenError:
            return True

    def force_close(self, url_or_domain: str) -> None:
        """Forca fechamento do circuito (uso administrativo)."""
        domain = _normalize_domain(url_or_domain)
        info = CircuitInfo(domain=domain, state=CircuitState.CLOSED.value)
        self._store(info)
        logger.info(f"Circuit force CLOSED | domain={domain}")

    def stats(self, url_or_domain: Optional[str] = None) -> dict:
        """Retorna metricas. Se domain nao fornecido, retorna apenas memoria local."""
        if url_or_domain is not None:
            domain = _normalize_domain(url_or_domain)
            info = self._load(domain)
            return asdict(info)

        with self._memory_lock:
            return {d: asdict(i) for d, i in self._memory.items()}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_domain(url_or_domain: str) -> str:
    """Extrai dominio canonico de uma URL ou retorna o input lower-cased."""
    if not url_or_domain:
        return "unknown"
    if "://" in url_or_domain:
        try:
            netloc = urlparse(url_or_domain).netloc
            return (netloc.split(":")[0] or url_or_domain).lower()
        except Exception:
            return url_or_domain.lower()
    return url_or_domain.split("/")[0].split(":")[0].lower()
