"""
NEXUS - Redis Client
=====================
Conexão centralizada com Redis.
Fallback automático para in-memory se Redis não estiver disponível.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client = None
_redis_available = False


def get_redis():
    """Retorna cliente Redis (singleton). None se não disponível."""
    global _redis_client, _redis_available

    if _redis_client is not None:
        return _redis_client if _redis_available else None

    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        logger.info("REDIS_URL não configurada — usando fallback in-memory")
        _redis_available = False
        _redis_client = False  # Marca como tentado
        return None

    try:
        import redis as redis_lib  # type: ignore[import-unresolved]
        _redis_client = redis_lib.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
        )
        # Testar conexão
        _redis_client.ping()
        _redis_available = True
        logger.info(f"✅ Redis conectado: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
        return _redis_client
    except Exception as e:
        logger.warning(f"⚠️ Redis indisponível ({e}) — usando fallback in-memory")
        _redis_available = False
        _redis_client = False
        return None


def redis_available() -> bool:
    """Verifica se Redis está disponível."""
    get_redis()  # Garante inicialização
    return _redis_available


def reset_redis():
    """Reset para testes."""
    global _redis_client, _redis_available
    _redis_client = None
    _redis_available = False
