"""
NEXUS - Rate Limiting por Plano
================================
Middleware + dependency de rate limiting baseado no plano do usuário.
Usa Redis (sorted sets) quando disponível, fallback para janela deslizante em memória.
"""

import os
import time
import threading
from collections import defaultdict
from typing import Any, Optional

from fastapi import HTTPException, Request, Depends, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURAÇÃO DE LIMITES POR PLANO
# ============================================================================

RATE_LIMITS: dict[str, dict[str, int]] = {
    "free": {
        "requests_per_minute": 20,
        "requests_per_hour": 200,
        "requests_per_day": 1000,
    },
    "pro": {
        "requests_per_minute": 60,
        "requests_per_hour": 2000,
        "requests_per_day": 10000,
    },
    "enterprise": {
        "requests_per_minute": 200,
        "requests_per_hour": 10000,
        "requests_per_day": 100000,
    },
}

# Limites para não-autenticados (por IP)
ANON_LIMITS = {
    "requests_per_minute": 10,
    "requests_per_hour": 60,
}

# Limites específicos para endpoints de auth (anti brute-force)
AUTH_LIMITS = {
    "/api/auth/login": {"per_minute": 5, "per_hour": 30},
    "/api/auth/signup": {"per_minute": 3, "per_hour": 20},
    "/api/auth/forgot-password": {"per_minute": 2, "per_hour": 10},
    "/api/auth/reset-password": {"per_minute": 3, "per_hour": 15},
}


# ============================================================================
# SLIDING WINDOW COUNTER (in-memory, thread-safe)
# ============================================================================

class SlidingWindowCounter:
    """Contador de janela deslizante para rate limiting."""

    def __init__(self):
        self._lock = threading.Lock()
        # key → list of timestamps
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def _cleanup_old(self, key: str, window_seconds: float, now: float) -> None:
        """Remove timestamps fora da janela."""
        cutoff = now - window_seconds
        timestamps = self._windows[key]
        # Busca binária simplificada — lista é ordenada
        i = 0
        while i < len(timestamps) and timestamps[i] < cutoff:
            i += 1
        if i > 0:
            self._windows[key] = timestamps[i:]

    def check_and_increment(
        self, key: str, window_seconds: float, max_requests: int
    ) -> tuple[bool, int, int]:
        """
        Verifica se pode fazer request e incrementa.
        Returns: (allowed, current_count, remaining)
        """
        now = time.time()
        with self._lock:
            self._cleanup_old(key, window_seconds, now)
            current = len(self._windows[key])
            if current >= max_requests:
                return False, current, 0
            self._windows[key].append(now)
            remaining = max_requests - current - 1
            return True, current + 1, remaining

    def get_count(self, key: str, window_seconds: float) -> int:
        """Retorna contagem atual na janela."""
        now = time.time()
        with self._lock:
            self._cleanup_old(key, window_seconds, now)
            return len(self._windows[key])

    def periodic_cleanup(self) -> None:
        """Limpeza periódica de chaves antigas (chamar a cada ~5 min)."""
        now = time.time()
        if now - self._last_cleanup < 300:
            return
        with self._lock:
            self._last_cleanup = now
            stale_keys = [
                k for k, v in self._windows.items()
                if not v or v[-1] < now - 86400
            ]
            for k in stale_keys:
                del self._windows[k]


# ============================================================================
# REDIS-BACKED SLIDING WINDOW (sorted sets)
# ============================================================================

class RedisSlidingWindow:
    """Rate limiting via Redis sorted sets — compartilhado entre workers."""

    def __init__(self, redis_client):
        self._redis = redis_client

    def check_and_increment(
        self, key: str, window_seconds: float, max_requests: int
    ) -> tuple[bool, int, int]:
        now = time.time()
        pipe = self._redis.pipeline()
        redis_key = f"rl:{key}"
        cutoff = now - window_seconds

        pipe.zremrangebyscore(redis_key, 0, cutoff)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {f"{now}": now})
        pipe.expire(redis_key, int(window_seconds) + 10)

        results = pipe.execute()
        current = results[1]  # zcard antes do zadd

        if current >= max_requests:
            # Desfazer o zadd
            self._redis.zrem(redis_key, f"{now}")
            return False, current, 0

        remaining = max_requests - current - 1
        return True, current + 1, remaining

    def get_count(self, key: str, window_seconds: float) -> int:
        now = time.time()
        redis_key = f"rl:{key}"
        self._redis.zremrangebyscore(redis_key, 0, now - window_seconds)
        return self._redis.zcard(redis_key)

    def periodic_cleanup(self) -> None:
        """Noop — Redis TTL cuida da limpeza."""
        pass


def _get_counter():
    """Retorna o counter apropriado: Redis ou in-memory."""
    try:
        from app.api.redis_client import get_redis  # type: ignore[import]
        r = get_redis()
        if r:
            return RedisSlidingWindow(r)
    except Exception:
        pass
    return SlidingWindowCounter()


# Instância global (in-memory, sempre disponível)
_counter = SlidingWindowCounter()

# Tentar trocar por Redis ao primeiro uso
_redis_counter: Optional[RedisSlidingWindow] = None
_redis_checked = False


def _get_active_counter():
    """Retorna Redis counter se disponível, senão in-memory."""
    global _redis_counter, _redis_checked
    if not _redis_checked:
        _redis_checked = True
        try:
            from app.api.redis_client import get_redis  # type: ignore[import]
            r = get_redis()
            if r:
                _redis_counter = RedisSlidingWindow(r)
                logger.info("✅ Rate limiting usando Redis")
        except Exception as e:
            logger.debug(f"Redis não disponível para rate limiting: {e}")
    return _redis_counter or _counter


# ============================================================================
# MIDDLEWARE DE RATE LIMITING
# ============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware que aplica rate limiting por IP para rotas públicas.
    Para rotas autenticadas, o rate limit por plano é aplicado via dependency.
    """

    # Rotas que não sofrem rate limiting
    EXEMPT_PATHS = {"/health", "/", "/openapi.json", "/docs", "/redoc"}
    EXEMPT_PREFIXES = ("/docs",)

    # Rotas de auth com rate limit agressivo
    AUTH_RATE_LIMITED = {
        "/api/auth/login", "/api/auth/signup",
        "/api/auth/forgot-password", "/api/auth/reset-password",
    }

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        path = request.url.path

        # Desabilitar rate limiting em testes
        if os.environ.get("ENVIRONMENT") == "test":
            return await call_next(request)

        # Rotas isentas
        if path in self.EXEMPT_PATHS:
            return await call_next(request)
        for prefix in self.EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Rate limit agressivo para endpoints de auth
        if path in self.AUTH_RATE_LIMITED:
            client_ip = request.client.host if request.client else "unknown"
            key = f"auth:{client_ip}:{path}"
            counter = _get_active_counter()
            limits = AUTH_LIMITS.get(path, {"per_minute": 5, "per_hour": 30})

            allowed, count, remaining = counter.check_and_increment(
                f"{key}:min", 60, limits["per_minute"]
            )
            if not allowed:
                logger.warning(f"Rate limit auth excedido: {client_ip} em {path}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "detail": "Muitas tentativas. Aguarde antes de tentar novamente.",
                        "retry_after": 60,
                    },
                    headers={"Retry-After": "60"},
                )

            allowed_hr, _, _ = counter.check_and_increment(
                f"{key}:hr", 3600, limits["per_hour"]
            )
            if not allowed_hr:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "detail": "Limite por hora excedido. Tente novamente mais tarde.",
                        "retry_after": 3600,
                    },
                    headers={"Retry-After": "3600"},
                )

            return await call_next(request)

        # Para rotas públicas (sem auth), limitar por IP
        if not request.headers.get("authorization"):
            client_ip = request.client.host if request.client else "unknown"
            key = f"anon:{client_ip}"
            counter = _get_active_counter()

            # Verificar limite por minuto
            allowed, count, remaining = counter.check_and_increment(
                f"{key}:min", 60, ANON_LIMITS["requests_per_minute"]
            )
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "detail": "Muitas requisições. Tente novamente em 1 minuto.",
                        "retry_after": 60,
                    },
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(ANON_LIMITS["requests_per_minute"]),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(ANON_LIMITS["requests_per_minute"])
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response

        # Rotas autenticadas passam — rate limit aplicado via dependency
        counter = _get_active_counter()
        counter.periodic_cleanup()
        return await call_next(request)


# ============================================================================
# DEPENDENCY para Rate Limiting autenticado
# ============================================================================

def get_rate_limit_key(user_id: int, plan: str) -> str:
    return f"user:{user_id}"


def check_rate_limit(current_user: dict[str, Any]) -> dict[str, Any]:
    """
    FastAPI Dependency — verifica rate limits do usuário autenticado.
    Usar como: Depends(check_rate_limit)
    """
    user_id = current_user.get("user_id", 0)
    plan = current_user.get("plan", "free")
    limits = RATE_LIMITS.get(plan, RATE_LIMITS["free"])
    key = f"user:{user_id}"
    counter = _get_active_counter()

    # Verificar limite por minuto
    allowed_min, count_min, remaining_min = counter.check_and_increment(
        f"{key}:min", 60, limits["requests_per_minute"]
    )
    if not allowed_min:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "detail": f"Limite de {limits['requests_per_minute']} req/min excedido. Aguarde.",
                "plan": plan,
                "limit": limits["requests_per_minute"],
                "window": "1 minuto",
                "retry_after": 60,
            },
            headers={"Retry-After": "60"},
        )

    # Verificar limite por hora
    allowed_hr, count_hr, remaining_hr = counter.check_and_increment(
        f"{key}:hr", 3600, limits["requests_per_hour"]
    )
    if not allowed_hr:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "detail": f"Limite de {limits['requests_per_hour']} req/hora excedido.",
                "plan": plan,
                "limit": limits["requests_per_hour"],
                "window": "1 hora",
                "retry_after": 3600,
                "upgrade_hint": "Faça upgrade para um plano maior" if plan == "free" else None,
            },
            headers={"Retry-After": "3600"},
        )

    return {
        **current_user,
        "rate_limit": {
            "plan": plan,
            "minute": {"used": count_min, "limit": limits["requests_per_minute"], "remaining": remaining_min},
            "hour": {"used": count_hr, "limit": limits["requests_per_hour"], "remaining": remaining_hr},
        },
    }


def get_rate_limit_info(plan: str = "free") -> dict[str, Any]:
    """Retorna informações de rate limit para exibição."""
    limits = RATE_LIMITS.get(plan, RATE_LIMITS["free"])
    return {
        "plan": plan,
        "limits": limits,
    }
