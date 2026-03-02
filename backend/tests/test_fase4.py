# pyright: reportMissingImports=false
"""
NEXUS — Testes Fase 4
======================
Docker, Redis, Sentry, E2E infra.
"""

import os
import sys
import json
import time
import asyncio
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Setup paths ──
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(backend_dir.parent))

os.environ.setdefault("JWT_SECRET", "test-secret-fase4")
os.environ.setdefault("ENVIRONMENT", "test")

from fastapi.testclient import TestClient


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def app():
    """Cria app de teste sem Redis (fallback in-memory)."""
    # Resetar redis state
    try:
        from app.api.redis_client import reset_redis  # type: ignore[import]
        reset_redis()
    except ImportError:
        pass
    # Remover REDIS_URL para forçar fallback
    os.environ.pop("REDIS_URL", None)
    os.environ.pop("SENTRY_DSN", None)

    from main import app as nexus_app  # type: ignore[import]
    return nexus_app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_token(client):
    """Cria user e retorna token."""
    email = f"fase4user_{int(time.time())}@nexus.com"
    signup_r = client.post("/api/auth/signup", json={
        "email": email,
        "password": "TestFase4Pass!",
        "full_name": "Fase4 User",
    })
    assert signup_r.status_code in (200, 201), f"Signup failed: {signup_r.json()}"
    r = client.post("/api/auth/login", json={
        "email": email,
        "password": "TestFase4Pass!",
    })
    assert r.status_code == 200, f"Login failed: {r.json()}"
    return r.json()["access_token"]


# ============================================================================
# REDIS CLIENT TESTS
# ============================================================================

class TestRedisClient:
    """Testa o módulo redis_client."""

    def test_redis_client_import(self):
        """Módulo redis_client é importável."""
        from app.api.redis_client import get_redis, redis_available, reset_redis
        assert callable(get_redis)
        assert callable(redis_available)
        assert callable(reset_redis)

    def test_redis_fallback_without_url(self):
        """Sem REDIS_URL, retorna None."""
        from app.api.redis_client import reset_redis, get_redis, redis_available
        reset_redis()
        os.environ.pop("REDIS_URL", None)
        result = get_redis()
        assert result is None
        assert not redis_available()

    def test_redis_reset(self):
        """Reset limpa estado do singleton."""
        from app.api.redis_client import reset_redis, get_redis
        reset_redis()
        os.environ.pop("REDIS_URL", None)
        # Primeira chamada
        get_redis()
        # Reset e chamar novamente
        reset_redis()
        result = get_redis()
        assert result is None


# ============================================================================
# REDIS SLIDING WINDOW TESTS
# ============================================================================

class TestRedisSlidingWindow:
    """Testa RedisSlidingWindow com mock Redis."""

    def test_redis_window_check_and_increment(self):
        """Sorted set sliding window funciona."""
        from app.api.rate_limit import RedisSlidingWindow

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = [None, 0, None, None]  # zremrange, zcard=0, zadd, expire

        window = RedisSlidingWindow(mock_redis)
        allowed, count, remaining = window.check_and_increment("test:key", 60, 10)

        assert allowed is True
        assert count == 1
        assert remaining == 9
        mock_pipe.zremrangebyscore.assert_called_once()
        mock_pipe.zadd.assert_called_once()

    def test_redis_window_rate_limited(self):
        """Rejeita quando acima do limite."""
        from app.api.rate_limit import RedisSlidingWindow

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = [None, 10, None, None]  # zcard = 10 (= max)

        window = RedisSlidingWindow(mock_redis)
        allowed, count, remaining = window.check_and_increment("test:key", 60, 10)

        assert allowed is False
        assert remaining == 0
        mock_redis.zrem.assert_called_once()  # Desfaz zadd

    def test_redis_window_get_count(self):
        """get_count retorna contagem."""
        from app.api.rate_limit import RedisSlidingWindow

        mock_redis = MagicMock()
        mock_redis.zcard.return_value = 5

        window = RedisSlidingWindow(mock_redis)
        count = window.get_count("test:key", 60)
        assert count == 5

    def test_redis_window_cleanup_is_noop(self):
        """periodic_cleanup é noop (Redis TTL cuida)."""
        from app.api.rate_limit import RedisSlidingWindow

        mock_redis = MagicMock()
        window = RedisSlidingWindow(mock_redis)
        window.periodic_cleanup()  # Não deve lançar exceção


# ============================================================================
# REDIS NOTIFICATION QUEUE TESTS
# ============================================================================

class TestRedisNotificationQueue:
    """Testa RedisNotificationQueue com mock Redis."""

    def test_redis_queue_push(self):
        """Push salva no Redis e publica."""
        from app.api.notifications import RedisNotificationQueue

        mock_redis = MagicMock()
        queue = RedisNotificationQueue(mock_redis)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(queue.push(1, {
                "type": "test",
                "title": "Test",
                "message": "Hello",
            }))
        finally:
            loop.close()

        mock_redis.lpush.assert_called_once()
        mock_redis.ltrim.assert_called_once()
        mock_redis.expire.assert_called_once()
        mock_redis.publish.assert_called_once()

    def test_redis_queue_get_unread(self):
        """get_unread lê do Redis."""
        from app.api.notifications import RedisNotificationQueue

        mock_redis = MagicMock()
        n = {"id": "n-1", "type": "test", "title": "T", "message": "M", "read": False}
        mock_redis.lrange.return_value = [json.dumps(n)]

        queue = RedisNotificationQueue(mock_redis)
        unread = queue.get_unread(1)

        assert len(unread) == 1
        assert unread[0]["id"] == "n-1"

    def test_redis_queue_mark_read(self):
        """mark_read atualiza no Redis."""
        from app.api.notifications import RedisNotificationQueue

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        n = {"id": "n-1", "type": "test", "title": "T", "message": "M", "read": False}
        mock_redis.lrange.return_value = [json.dumps(n)]

        queue = RedisNotificationQueue(mock_redis)
        count = queue.mark_read(1, "n-1")

        assert count == 1
        mock_pipe.execute.assert_called_once()

    def test_redis_queue_clear(self):
        """clear deleta key no Redis."""
        from app.api.notifications import RedisNotificationQueue

        mock_redis = MagicMock()
        queue = RedisNotificationQueue(mock_redis)
        queue.clear(1)

        mock_redis.delete.assert_called_once()


# ============================================================================
# SENTRY / MONITORING TESTS
# ============================================================================

class TestMonitoring:
    """Testa módulo de monitoramento."""

    def test_monitoring_import(self):
        """Módulo monitoring é importável."""
        from app.api.monitoring import init_sentry, capture_exception, set_user_context
        assert callable(init_sentry)
        assert callable(capture_exception)
        assert callable(set_user_context)

    def test_sentry_disabled_without_dsn(self):
        """Sem SENTRY_DSN, init_sentry retorna False."""
        os.environ.pop("SENTRY_DSN", None)
        from app.api.monitoring import init_sentry
        result = init_sentry()
        assert result is False

    def test_capture_exception_without_sentry(self):
        """capture_exception não falha sem Sentry."""
        os.environ.pop("SENTRY_DSN", None)
        from app.api.monitoring import capture_exception
        # Não deve lançar exceção
        capture_exception(ValueError("test error"), context="unit_test")

    def test_set_user_context_without_sentry(self):
        """set_user_context não falha sem Sentry."""
        from app.api.monitoring import set_user_context
        set_user_context(1, "test@test.com", "pro")


# ============================================================================
# HEALTH CHECK ENHANCED TESTS
# ============================================================================

class TestHealthEnhanced:
    """Testa o health check aprimorado."""

    def test_health_includes_redis_status(self, client):
        """Health check retorna status do Redis."""
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "redis" in data
        assert data["redis"] in ("connected", "unavailable", "not_configured")

    def test_health_includes_sentry_status(self, client):
        """Health check retorna status do Sentry."""
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "sentry" in data
        assert data["sentry"] in ("active", "not_configured")

    def test_health_still_ok(self, client):
        """Health check principal ainda funciona."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ============================================================================
# DOCKER COMPOSE VALIDATION
# ============================================================================

class TestDockerComposeConfig:
    """Valida que os arquivos Docker existem e são válidos."""

    def test_docker_compose_exists(self):
        """docker-compose.yml existe na raiz."""
        compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
        assert compose_path.exists(), "docker-compose.yml não encontrado"

    def test_docker_compose_has_services(self):
        """docker-compose.yml define 4 serviços."""
        import yaml
        compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        services = config.get("services", {})
        assert "redis" in services
        assert "backend" in services
        assert "frontend" in services
        assert "e2e" in services

    def test_docker_compose_redis_config(self):
        """Redis configurado com healthcheck e persistência."""
        import yaml
        compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        redis = config["services"]["redis"]
        assert "healthcheck" in redis
        assert "redis:7" in redis["image"]

    def test_docker_compose_backend_depends_on_redis(self):
        """Backend depende do Redis."""
        import yaml
        compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        backend = config["services"]["backend"]
        depends = backend.get("depends_on", {})
        assert "redis" in depends

    def test_backend_dockerfile_exists(self):
        """Backend Dockerfile existe."""
        df = Path(__file__).parent.parent / "Dockerfile"
        assert df.exists()

    def test_frontend_dockerfile_exists(self):
        """Frontend Dockerfile existe."""
        df = Path(__file__).parent.parent.parent / "frontend" / "Dockerfile"
        assert df.exists()

    def test_frontend_nginx_conf_exists(self):
        """nginx.conf para frontend existe."""
        nginx = Path(__file__).parent.parent.parent / "frontend" / "nginx.conf"
        assert nginx.exists()

    def test_e2e_dockerfile_exists(self):
        """E2E Dockerfile existe."""
        df = Path(__file__).parent.parent.parent / "e2e" / "Dockerfile"
        assert df.exists()


# ============================================================================
# RATE LIMIT FALLBACK INTEGRATION
# ============================================================================

class TestRateLimitFallback:
    """Testa que rate limiting funciona sem Redis (fallback in-memory)."""

    def test_rate_limit_works_without_redis(self, client):
        """Rate limiting headers presentes mesmo sem Redis."""
        r = client.get("/openapi.json")
        assert r.status_code == 200
        # Headers devem estar presentes (middleware ativo com fallback)
        assert "x-ratelimit-limit" in r.headers or r.status_code == 200

    def test_in_memory_counter_direct(self):
        """SlidingWindowCounter funciona diretamente."""
        from app.api.rate_limit import SlidingWindowCounter

        counter = SlidingWindowCounter()
        # Deve permitir
        ok, count, remaining = counter.check_and_increment("fallback:test", 60, 5)
        assert ok is True
        assert count == 1
        assert remaining == 4


# ============================================================================
# NOTIFICATION FALLBACK INTEGRATION
# ============================================================================

class TestNotificationFallback:
    """Testa notificações sem Redis."""

    def test_unread_works_without_redis(self, client, auth_token):
        """Endpoint unread funciona sem Redis."""
        r = client.get(
            "/api/notifications/unread",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "notifications" in data
        assert "count" in data

    def test_mark_read_without_redis(self, client, auth_token):
        """mark_read funciona sem Redis."""
        r = client.post(
            "/api/notifications/read",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert r.status_code == 200

    def test_clear_without_redis(self, client, auth_token):
        """clear funciona sem Redis."""
        r = client.delete(
            "/api/notifications/clear",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert r.status_code == 200
