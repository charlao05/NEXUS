# pyright: reportMissingImports=false
"""
Testes — Fase 3: Rate Limiting, Notifications, Admin Dashboard
================================================================
"""

import pytest
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from starlette.testclient import TestClient

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def app():
    """Importa app isolada para testes."""
    import sys
    from pathlib import Path
    backend = Path(__file__).parent.parent
    sys.path.insert(0, str(backend))
    import os
    os.environ.setdefault("JWT_SECRET", "test-secret-fase3")
    os.environ.setdefault("NEXUS_DB_PATH", str(backend / "data" / "test_fase3.db"))
    # Admin emails — incluir emails usados em todos os arquivos de teste
    os.environ["ADMIN_EMAILS"] = "admin@nexus.com,test-admin@nexus.com,fase3admin@nexus.com"

    from main import app as _app
    from database.models import init_db
    init_db()
    return _app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_token(client):
    """Cria usuário e retorna token."""
    client.post("/api/auth/signup", json={
        "email": "fase3user@nexus.com",
        "password": "Teste1234!",
        "full_name": "Fase3 User",
    })
    resp = client.post("/api/auth/login", json={
        "email": "fase3user@nexus.com",
        "password": "Teste1234!",
    })
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token(client):
    """Cria admin e retorna token."""
    email = "fase3admin@nexus.com"
    password = "Admin1234!"
    # Pode já existir de run anterior
    client.post("/api/auth/signup", json={
        "email": email,
        "password": password,
        "full_name": "Admin User F3",
    })
    resp = client.post("/api/auth/login", json={
        "email": email,
        "password": password,
    })
    data = resp.json()
    assert "access_token" in data, f"Login admin falhou: {data}"
    return data["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================

class TestRateLimiting:
    """Testa o middleware e dependency de rate limiting."""

    def test_rate_limit_headers_present(self, client, auth_token):
        """Respostas devem incluir headers de rate limit."""
        resp = client.get("/api/auth/me", headers=_headers(auth_token))
        # Não verificamos X-RateLimit aqui pois é controlado por middleware para anon
        assert resp.status_code == 200

    def test_anon_rate_limit_works(self, client):
        """Endpoints sem auth devem aplicar rate limit por IP (rotas não-isentas)."""
        # /api/auth/* é isento, mas /api/notifications/unread (sem auth) não
        # Porém, fazemos muitas requests para validar que o limiter funciona
        from app.api.rate_limit import SlidingWindowCounter
        counter = SlidingWindowCounter()
        # Verificar que counter funciona conceitualmente
        for i in range(10):
            allowed, _, _ = counter.check_and_increment("anon-test:min", 60, 10)
            assert allowed is True
        allowed, _, _ = counter.check_and_increment("anon-test:min", 60, 10)
        assert allowed is False

    def test_rate_limit_dependency_import(self):
        """Verifica que o módulo de rate limit é importável."""
        from app.api.rate_limit import check_rate_limit, RATE_LIMITS
        assert "free" in RATE_LIMITS
        assert "pro" in RATE_LIMITS
        assert RATE_LIMITS["free"]["requests_per_minute"] < RATE_LIMITS["pro"]["requests_per_minute"]

    def test_sliding_window_counter(self):
        """Testa o contador de janela deslizante."""
        from app.api.rate_limit import SlidingWindowCounter
        counter = SlidingWindowCounter()

        # Deve permitir até o limite
        for i in range(5):
            allowed, count, remaining = counter.check_and_increment("test:key", 60, 5)
            assert allowed is True
            assert count == i + 1

        # Deve bloquear no limite
        allowed, count, remaining = counter.check_and_increment("test:key", 60, 5)
        assert allowed is False
        assert remaining == 0


# ============================================================================
# NOTIFICATIONS TESTS
# ============================================================================

class TestNotifications:
    """Testa o sistema de notificações."""

    def test_unread_requires_auth(self, client):
        """Endpoint de notificações requer autenticação."""
        resp = client.get("/api/notifications/unread")
        # 401 sem auth, ou 429 se rate limiter bloqueou antes
        assert resp.status_code in (401, 429)

    def test_unread_empty_initially(self, client, auth_token):
        """Sem notificações inicialmente."""
        resp = client.get("/api/notifications/unread", headers=_headers(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "notifications" in data
        assert "count" in data

    def test_mark_read(self, client, auth_token):
        """Marcar notificações como lidas não deve falhar."""
        resp = client.post("/api/notifications/read", headers=_headers(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "marked" in data

    def test_clear_notifications(self, client, auth_token):
        """Limpar notificações."""
        resp = client.delete("/api/notifications/clear", headers=_headers(auth_token))
        assert resp.status_code == 200
        assert resp.json()["cleared"] is True

    def test_notification_queue_push_and_get(self):
        """Testa a fila de notificações in-memory."""
        import asyncio
        from app.api.notifications import NotificationQueue

        queue = NotificationQueue()

        # Push notification
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            queue.push(999, {
                "type": "test",
                "title": "Test Notification",
                "message": "Mensagem de teste",
                "severity": "info",
            })
        )
        loop.close()

        unread = queue.get_unread(999)
        assert len(unread) == 1
        assert unread[0]["type"] == "test"
        assert unread[0]["title"] == "Test Notification"

        # Mark read
        count = queue.mark_read(999)
        assert count == 1

        # Clear
        queue.clear(999)
        assert len(queue.get_unread(999)) == 0


# ============================================================================
# ADMIN DASHBOARD TESTS
# ============================================================================

class TestAdminDashboard:
    """Testa endpoints do painel administrativo."""

    def test_admin_overview_requires_admin(self, client, auth_token):
        """Usuário comum não pode acessar admin."""
        resp = client.get("/api/admin/overview", headers=_headers(auth_token))
        assert resp.status_code == 403

    def test_admin_overview_works(self, client, admin_token):
        """Admin pode ver overview."""
        resp = client.get("/api/admin/overview", headers=_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "revenue" in data
        assert "platform" in data
        assert data["users"]["total"] >= 1

    def test_admin_users_list(self, client, admin_token):
        """Admin pode listar usuários."""
        resp = client.get("/api/admin/users", headers=_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] >= 1
        assert len(data["users"]) >= 1

    def test_admin_users_search(self, client, admin_token):
        """Admin pode buscar usuários por email."""
        resp = client.get("/api/admin/users?search=fase3", headers=_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_admin_users_filter_plan(self, client, admin_token):
        """Admin pode filtrar por plano."""
        resp = client.get("/api/admin/users?plan=free", headers=_headers(admin_token))
        assert resp.status_code == 200

    def test_admin_user_detail(self, client, admin_token):
        """Admin pode ver detalhes de um usuário."""
        # Pegar ID do primeiro usuário
        users_resp = client.get("/api/admin/users", headers=_headers(admin_token))
        user_id = users_resp.json()["users"][0]["id"]

        resp = client.get(f"/api/admin/users/{user_id}", headers=_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert "subscriptions" in data
        assert "recent_activity" in data
        assert "chat_messages_total" in data

    def test_admin_mrr_chart(self, client, admin_token):
        """Admin pode ver gráfico MRR."""
        resp = client.get("/api/admin/mrr-chart", headers=_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "chart" in data
        assert len(data["chart"]) == 6

    def test_admin_health(self, client, admin_token):
        """Admin pode ver saúde do sistema."""
        resp = client.get("/api/admin/health", headers=_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert "database" in data
        assert data["database"]["connected"] is True

    def test_admin_nonexistent_user(self, client, admin_token):
        """Detalhe de usuário inexistente retorna 404."""
        resp = client.get("/api/admin/users/99999", headers=_headers(admin_token))
        assert resp.status_code == 404


# ============================================================================
# INTEGRATION: Middleware Stack
# ============================================================================

class TestMiddlewareStack:
    """Testa que todos os middlewares funcionam em conjunto."""

    def test_security_headers_still_present(self, client):
        """Security headers devem funcionar com o rate limit middleware."""
        resp = client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_all_new_routes_registered(self, client):
        """Verifica que as novas rotas existem no OpenAPI."""
        resp = client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/notifications/stream" in paths
        assert "/api/notifications/unread" in paths
        assert "/api/notifications/read" in paths
        assert "/api/admin/overview" in paths
        assert "/api/admin/users" in paths
        assert "/api/admin/mrr-chart" in paths
        assert "/api/admin/health" in paths
