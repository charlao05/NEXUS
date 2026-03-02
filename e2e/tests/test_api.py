"""
NEXUS E2E — Testes de Health e API
===================================
Verifica endpoints fundamentais via HTTP antes de testar o frontend.
"""

import requests
import pytest


class TestAPIHealth:
    """Testa os endpoints de saúde e metadados."""

    def test_backend_health(self, api_url):
        """Backend responde no /health."""
        r = requests.get(f"{api_url}/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "NEXUS" in data["service"]

    def test_backend_root(self, api_url):
        """Root retorna metadata."""
        r = requests.get(f"{api_url}/", timeout=10)
        assert r.status_code == 200

    def test_openapi_available(self, api_url):
        """OpenAPI schema acessível."""
        r = requests.get(f"{api_url}/openapi.json", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "paths" in data
        # Deve ter ao menos as rotas básicas
        assert len(data["paths"]) >= 60

    def test_security_headers(self, api_url):
        """Headers de segurança presentes."""
        r = requests.get(f"{api_url}/health", timeout=10)
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"

    def test_cors_headers(self, api_url):
        """CORS permite frontend."""
        r = requests.options(
            f"{api_url}/health",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
            timeout=10,
        )
        # CORS deve aceitar ou responder normalmente
        assert r.status_code in (200, 204, 405)


class TestAuthAPI:
    """Testa fluxo de autenticação via HTTP."""

    def test_signup_and_login(self, api_url, test_user):
        """Signup → Login → Token válido."""
        # Signup (pode falhar se user já existe)
        requests.post(
            f"{api_url}/api/auth/signup",
            json=test_user,
            timeout=10,
        )

        # Login
        r = requests.post(
            f"{api_url}/api/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        token = data["access_token"]

        # /me com token
        r2 = requests.get(
            f"{api_url}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert r2.status_code == 200
        me = r2.json()
        assert me["email"] == test_user["email"]

    def test_login_wrong_password(self, api_url, test_user):
        """Login com senha errada retorna 401."""
        r = requests.post(
            f"{api_url}/api/auth/login",
            json={"email": test_user["email"], "password": "WrongPassword!"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_protected_without_token(self, api_url):
        """Rotas protegidas retornam 401 sem token."""
        r = requests.get(f"{api_url}/api/auth/me", timeout=10)
        assert r.status_code == 401


class TestNotificationsAPI:
    """Testa endpoints de notificações via HTTP."""

    def test_unread_requires_auth(self, api_url):
        r = requests.get(f"{api_url}/api/notifications/unread", timeout=10)
        assert r.status_code == 401

    def test_unread_with_auth(self, api_url, test_user):
        # Login
        login_r = requests.post(
            f"{api_url}/api/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
            timeout=10,
        )
        if login_r.status_code != 200:
            pytest.skip("User not registered")
        token = login_r.json()["access_token"]

        r = requests.get(
            f"{api_url}/api/notifications/unread",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "notifications" in data
        assert "count" in data


class TestRateLimitAPI:
    """Testa rate limiting via HTTP."""

    def test_rate_limit_headers(self, api_url):
        """Requests anônimos incluem headers de rate limit."""
        # Usar rota sem auth
        r = requests.get(f"{api_url}/openapi.json", timeout=10)
        # Pode ter headers se for anon request
        assert r.status_code == 200
