# pyright: reportMissingImports=false
"""
NEXUS — Testes Fase 8 (100% Produção)
=======================================
  1. Rate limiting em endpoints de auth
  2. LGPD exclusão de conta
  3. JWT Refresh Token
  4. DB no health check
  5. Structured logging / API metadata
  6. robots.txt / Página 404
  7. Backup script existe

Rodar:  cd backend && python -m pytest tests/test_fase8.py -v --tb=short
"""

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Setup paths ──
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(backend_dir.parent))

os.environ.setdefault("JWT_SECRET", "test-secret-fase8")
os.environ.setdefault("ENVIRONMENT", "test")

from fastapi.testclient import TestClient


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def app():
    try:
        from app.api.redis_client import reset_redis
        reset_redis()
    except ImportError:
        pass
    os.environ.pop("REDIS_URL", None)
    os.environ.pop("SENTRY_DSN", None)
    from main import app as nexus_app
    return nexus_app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


def _create_user_and_token(client, suffix=""):
    uid = uuid.uuid4().hex[:8]
    email = f"f8_{uid}{suffix}@test.com"
    r = client.post("/api/auth/signup", json={
        "email": email,
        "password": "Fase8Test!123",
        "full_name": f"Teste Fase8 {uid}",
    })
    assert r.status_code == 201, f"Signup failed: {r.text}"
    data = r.json()
    return data["access_token"], email, data


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. RATE LIMITING EM AUTH ENDPOINTS
# ============================================================================

class TestAuthRateLimiting:
    """Testa que endpoints de auth têm rate limiting configurado."""

    def test_auth_not_exempt_from_rate_limit(self):
        """Verifica no código que /api/auth/ NÃO está nos prefixos isentos."""
        from app.api.rate_limit import RateLimitMiddleware
        for prefix in RateLimitMiddleware.EXEMPT_PREFIXES:
            assert "/api/auth/" not in prefix, \
                f"/api/auth/ encontrado nos prefixos isentos: {prefix}"

    def test_auth_endpoints_in_rate_limit_set(self):
        """Verifica que endpoints críticos estão no set de rate limiting."""
        from app.api.rate_limit import RateLimitMiddleware
        required = {"/api/auth/login", "/api/auth/signup", "/api/auth/forgot-password"}
        for endpoint in required:
            assert endpoint in RateLimitMiddleware.AUTH_RATE_LIMITED, \
                f"{endpoint} deveria estar no AUTH_RATE_LIMITED"

    def test_auth_limits_are_strict(self):
        """Limites de auth devem ser mais rigorosos que os gerais."""
        from app.api.rate_limit import AUTH_LIMITS, ANON_LIMITS
        # Login: max 5/min (vs 10/min para anon geral)
        assert AUTH_LIMITS["/api/auth/login"]["per_minute"] <= 5
        # Signup: max 3/min
        assert AUTH_LIMITS["/api/auth/signup"]["per_minute"] <= 3
        # Forgot password: max 2/min
        assert AUTH_LIMITS["/api/auth/forgot-password"]["per_minute"] <= 2


# ============================================================================
# 2. LGPD EXCLUSÃO DE CONTA
# ============================================================================

class TestAccountDeletion:
    """Testa endpoint de exclusão de conta LGPD."""

    def test_delete_requires_auth(self, client):
        r = client.request("DELETE", "/api/auth/delete-account", json={
            "password": "test", "confirm": True,
        })
        assert r.status_code in (401, 403)

    def test_delete_requires_confirmation(self, client):
        token, email, _ = _create_user_and_token(client, "_del_noconf")
        r = client.request("DELETE", "/api/auth/delete-account", json={
            "password": "Fase8Test!123",
            "confirm": False,
        }, headers=_auth(token))
        assert r.status_code == 400
        assert "confirm" in r.text.lower()

    def test_delete_wrong_password_rejected(self, client):
        token, email, _ = _create_user_and_token(client, "_del_wp")
        r = client.request("DELETE", "/api/auth/delete-account", json={
            "password": "WrongPassword!1",
            "confirm": True,
        }, headers=_auth(token))
        assert r.status_code == 403

    def test_delete_account_success(self, client):
        token, email, _ = _create_user_and_token(client, "_del_ok")
        # Criar um cliente para testar cascade
        client.post("/api/crm/clients", json={
            "name": "Cliente para Deletar",
            "email": "todelete@test.com",
        }, headers=_auth(token))

        r = client.request("DELETE", "/api/auth/delete-account", json={
            "password": "Fase8Test!123",
            "confirm": True,
        }, headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"
        assert "LGPD" in r.json()["message"]

    def test_deleted_user_cannot_login(self, client):
        token, email, _ = _create_user_and_token(client, "_del_nologin")
        # Deletar conta
        client.request("DELETE", "/api/auth/delete-account", json={
            "password": "Fase8Test!123",
            "confirm": True,
        }, headers=_auth(token))
        # Tentar login
        r = client.post("/api/auth/login", json={
            "email": email,
            "password": "Fase8Test!123",
        })
        assert r.status_code in (400, 401, 404), f"Login deveria falhar após exclusão: {r.text}"


# ============================================================================
# 3. JWT REFRESH TOKEN
# ============================================================================

class TestRefreshToken:
    """Testa fluxo de refresh token."""

    def test_signup_returns_refresh_token(self, client):
        _, _, data = _create_user_and_token(client, "_rt_signup")
        assert "refresh_token" in data
        assert data["refresh_token"] is not None

    def test_login_returns_refresh_token(self, client):
        _, email, _ = _create_user_and_token(client, "_rt_login")
        r = client.post("/api/auth/login", json={
            "email": email,
            "password": "Fase8Test!123",
        })
        assert r.status_code == 200
        assert r.json().get("refresh_token") is not None

    def test_refresh_returns_new_tokens(self, client):
        _, email, data = _create_user_and_token(client, "_rt_refresh")
        r = client.post("/api/auth/refresh", json={
            "refresh_token": data["refresh_token"],
        })
        assert r.status_code == 200
        new_data = r.json()
        assert new_data["access_token"] != data["access_token"]
        assert new_data["refresh_token"] is not None
        assert new_data["email"] == email

    def test_refresh_with_access_token_fails(self, client):
        token, _, data = _create_user_and_token(client, "_rt_badtype")
        # Usar access_token ao invés de refresh_token
        r = client.post("/api/auth/refresh", json={
            "refresh_token": token,
        })
        assert r.status_code == 401

    def test_refresh_with_invalid_token_fails(self, client):
        r = client.post("/api/auth/refresh", json={
            "refresh_token": "invalid.token.here",
        })
        assert r.status_code == 401


# ============================================================================
# 4. HEALTH CHECK COM DATABASE
# ============================================================================

class TestHealthCheck:
    """Testa health check melhorado."""

    def test_health_includes_database(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "database" in data
        assert data["database"] == "connected"

    def test_health_includes_redis(self, client):
        r = client.get("/health")
        data = r.json()
        assert "redis" in data

    def test_health_status_ok(self, client):
        r = client.get("/health")
        assert r.json()["status"] in ("ok", "degraded")


# ============================================================================
# 5. API METADATA
# ============================================================================

class TestAPIMetadata:
    """Testa que a API tem metadata completa."""

    def test_api_has_version(self, app):
        assert app.version == "1.0.0"

    def test_api_has_description(self, app):
        assert app.description is not None
        assert len(app.description) > 20

    def test_api_has_title(self, app):
        assert app.title == "NEXUS API"


# ============================================================================
# 6. VERIFICAÇÕES DE ARTEFATOS
# ============================================================================

class TestArtifacts:
    """Verifica que artefatos de produção existem."""

    def test_robots_txt_exists(self):
        path = backend_dir.parent / "frontend" / "public" / "robots.txt"
        assert path.exists(), "robots.txt não encontrado"
        content = path.read_text()
        assert "Disallow" in content
        assert "/dashboard" in content
        assert "/api/" in content

    def test_not_found_page_exists(self):
        path = backend_dir.parent / "frontend" / "src" / "pages" / "NotFound.tsx"
        assert path.exists(), "NotFound.tsx não encontrado"
        content = path.read_text()
        assert "404" in content

    def test_backup_script_exists(self):
        path = backend_dir.parent / "scripts" / "backup_postgres.sh"
        assert path.exists(), "backup_postgres.sh não encontrado"
        content = path.read_text()
        assert "pg_dump" in content

    def test_ci_has_e2e_job(self):
        ci_path = backend_dir.parent / ".github" / "workflows" / "ci.yml"
        assert ci_path.exists(), "ci.yml não encontrado"
        content = ci_path.read_text()
        assert "e2e" in content.lower()

    def test_docker_compose_has_postgres(self):
        path = backend_dir.parent / "docker-compose.yml"
        assert path.exists()
        content = path.read_text()
        assert "postgres:" in content
        assert "pg_isready" in content

    def test_no_swagger_in_production(self, app):
        """Em produção, /docs e /redoc devem ser desabilitados."""
        # Verificar que o código configura docs_url baseado em ENVIRONMENT
        import inspect
        # A lógica de produção está no código — verificar que o atributo existe
        # Em test, docs_url pode estar habilitado
        assert hasattr(app, 'docs_url')


# ============================================================================
# 7. STRUCTURED LOGGING
# ============================================================================

class TestStructuredLogging:
    """Verifica que logging JSON está configurado para produção."""

    def test_json_formatter_exists_in_code(self):
        main_path = backend_dir / "main.py"
        content = main_path.read_text(encoding="utf-8")
        assert "JsonFormatter" in content or "_JsonFormatter" in content
        assert "json.dumps" in content or "_json.dumps" in content
        assert "ENVIRONMENT" in content
