# pyright: reportMissingImports=false
"""
NEXUS — Testes Fase 7
======================
Bloqueios Tier 2 para produção:
  1. Validação de inputs (Pydantic Field constraints)
  2. Senha mínima 8 caracteres
  3. CSP + Permissions-Policy headers
  4. LGPD data export endpoint
  5. user_id filter em interações
  6. CORS restrito / env validation (unitário)
  7. Sourcemaps off em produção (build check)
  8. dangerouslySetInnerHTML removido (verificação de código)

Rodar:  cd backend && python -m pytest tests/test_fase7.py -v --tb=short
"""

import os
import sys
import re
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Setup paths ──
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(backend_dir.parent))

os.environ.setdefault("JWT_SECRET", "test-secret-fase7")
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


_counter = 0
def _create_user_and_token(client, suffix=""):
    global _counter
    _counter += 1
    uid = uuid.uuid4().hex[:8]
    email = f"f7_{uid}{suffix}@test.com"
    r = client.post("/api/auth/signup", json={
        "email": email,
        "password": "Fase7Test!123",
        "full_name": f"Teste Fase7 {_counter}",
    })
    assert r.status_code == 201, f"Signup failed: {r.text}"
    token = r.json()["access_token"]
    return token, email


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. VALIDAÇÃO DE INPUTS — Pydantic Field constraints
# ============================================================================

class TestInputValidation:
    """Testa que inputs inválidos são rejeitados pelos modelos Pydantic."""

    def test_client_empty_name_rejected(self, client):
        token, _ = _create_user_and_token(client)
        r = client.post("/api/crm/clients", json={
            "name": "",  # min_length=1 → deve falhar
            "email": "a@b.com",
        }, headers=_auth(token))
        assert r.status_code == 422

    def test_client_name_too_long_rejected(self, client):
        token, _ = _create_user_and_token(client)
        r = client.post("/api/crm/clients", json={
            "name": "A" * 201,  # max_length=200
            "email": "a@b.com",
        }, headers=_auth(token))
        assert r.status_code == 422

    def test_client_invalid_email_rejected(self, client):
        token, _ = _create_user_and_token(client)
        r = client.post("/api/crm/clients", json={
            "name": "Teste",
            "email": "not-an-email",  # EmailStr → deve falhar
        }, headers=_auth(token))
        assert r.status_code == 422

    def test_client_invalid_segment_rejected(self, client):
        token, _ = _create_user_and_token(client)
        r = client.post("/api/crm/clients", json={
            "name": "Teste",
            "email": "a@b.com",
            "segment": "INVALIDO",  # Literal → deve falhar
        }, headers=_auth(token))
        assert r.status_code == 422

    def test_transaction_negative_amount_rejected(self, client):
        token, _ = _create_user_and_token(client)
        # Criar um cliente primeiro
        rc = client.post("/api/crm/clients", json={
            "name": "Cli Trans",
            "email": "trans@test.com",
        }, headers=_auth(token))
        assert rc.status_code == 200
        data = rc.json()
        cid = data.get("client_id") or data.get("id") or (data.get("client", {}).get("id"))
        r = client.post("/api/crm/transactions", json={
            "client_id": cid,
            "type": "receita",
            "amount": -100,  # gt=0 → deve falhar
            "description": "teste",
        }, headers=_auth(token))
        assert r.status_code == 422

    def test_transaction_invalid_type_rejected(self, client):
        token, _ = _create_user_and_token(client)
        r = client.post("/api/crm/transactions", json={
            "client_id": 1,
            "type": "invalido",  # Literal["receita","despesa"] → deve falhar
            "amount": 100,
            "description": "teste",
        }, headers=_auth(token))
        assert r.status_code == 422

    def test_opportunity_invalid_stage_rejected(self, client):
        token, _ = _create_user_and_token(client)
        r = client.post("/api/crm/opportunities", json={
            "client_id": 1,
            "title": "Deal",
            "stage": "inexistente",  # Literal → deve falhar
        }, headers=_auth(token))
        assert r.status_code == 422

    def test_interaction_invalid_channel_rejected(self, client):
        token, _ = _create_user_and_token(client)
        r = client.post("/api/crm/interactions", json={
            "client_id": 1,
            "type": "nota",
            "channel": "smoke_signal",  # Literal → deve falhar
            "summary": "teste",
        }, headers=_auth(token))
        assert r.status_code == 422

    def test_valid_client_accepted(self, client):
        token, _ = _create_user_and_token(client)
        r = client.post("/api/crm/clients", json={
            "name": "Cliente Válido",
            "email": "valido@test.com",
            "segment": "premium",
        }, headers=_auth(token))
        assert r.status_code == 200


# ============================================================================
# 2. SENHA MÍNIMA 8 CARACTERES
# ============================================================================

class TestPasswordPolicy:
    """Testa que senhas curtas são rejeitadas."""

    def test_signup_short_password_rejected(self, client):
        uid = uuid.uuid4().hex[:8]
        r = client.post("/api/auth/signup", json={
            "email": f"short_pw_{uid}@test.com",
            "password": "Ab1!xyz",  # 7 chars
            "full_name": "Short Pw",
        })
        assert r.status_code == 400
        assert "8" in r.text.lower() or "caractere" in r.text.lower()

    def test_signup_8char_password_accepted(self, client):
        uid = uuid.uuid4().hex[:8]
        r = client.post("/api/auth/signup", json={
            "email": f"ok_pw_{uid}@test.com",
            "password": "Ab1!xyzz",  # exatamente 8
            "full_name": "OK Pw",
        })
        assert r.status_code == 201


# ============================================================================
# 3. SECURITY HEADERS (CSP, Permissions-Policy)
# ============================================================================

class TestSecurityHeaders:
    """Testa headers de segurança adicionados pelo middleware."""

    def test_security_headers_present(self, client):
        r = client.get("/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"
        assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        # camera/microphone=(self) permite uso pela própria origem (Whisper audio transcription)
        assert r.headers.get("Permissions-Policy") == "camera=(self), microphone=(self), geolocation=()"

    def test_csp_in_production(self, client, app):
        """CSP header aparece em produção."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            r = client.get("/health")
            csp = r.headers.get("Content-Security-Policy", "")
            assert "default-src 'self'" in csp
            assert "script-src 'self'" in csp
            assert "object-src 'none'" in csp

    def test_hsts_in_production(self, client):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            r = client.get("/health")
            assert "max-age=" in (r.headers.get("Strict-Transport-Security") or "")


# ============================================================================
# 4. LGPD DATA EXPORT
# ============================================================================

class TestLGPDExport:
    """Testa endpoint de exportação de dados pessoais."""

    def test_export_requires_auth(self, client):
        r = client.get("/api/auth/export-my-data")
        assert r.status_code in (401, 403)

    def test_export_returns_profile(self, client):
        token, email = _create_user_and_token(client, "_export")
        r = client.get("/api/auth/export-my-data", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "profile" in data
        assert data["profile"]["email"] == email

    def test_export_contains_all_sections(self, client):
        token, _ = _create_user_and_token(client, "_sections")
        r = client.get("/api/auth/export-my-data", headers=_auth(token))
        data = r.json()
        for key in ("profile", "clients", "opportunities", "appointments", "notice"):
            assert key in data, f"Missing key: {key}"
        assert "LGPD" in data["notice"]


# ============================================================================
# 5. USER_ID FILTER EM INTERAÇÕES
# ============================================================================

class TestInteractionIsolation:
    """Testa que um usuário NÃO acessa interações de clientes de outro."""

    def test_interaction_on_other_users_client_rejected(self, client):
        # User 1 cria cliente
        token1, _ = _create_user_and_token(client, "_iso1")
        r1 = client.post("/api/crm/clients", json={
            "name": "Cliente User1",
            "email": "user1cli@test.com",
        }, headers=_auth(token1))
        assert r1.status_code == 200
        data = r1.json()
        cid = data.get("client_id") or data.get("id") or (data.get("client", {}).get("id"))
        assert cid is not None, f"Não conseguiu extrair client_id: {data}"

        # User 2 tenta criar interação no cliente do User 1
        token2, _ = _create_user_and_token(client, "_iso2")
        r2 = client.post("/api/crm/interactions", json={
            "client_id": cid,
            "type": "nota",
            "channel": "email",
            "summary": "Tentativa indevida",
        }, headers=_auth(token2))
        assert r2.status_code == 404, f"User2 não deveria acessar cliente de User1: {r2.text}"

    def test_get_interactions_other_user_rejected(self, client):
        token1, _ = _create_user_and_token(client, "_gi1")
        r1 = client.post("/api/crm/clients", json={
            "name": "Cli Interações",
            "email": "interacoes@test.com",
        }, headers=_auth(token1))
        data = r1.json()
        cid = data.get("client_id") or data.get("id") or (data.get("client", {}).get("id"))
        assert cid is not None

        token2, _ = _create_user_and_token(client, "_gi2")
        r2 = client.get(f"/api/crm/clients/{cid}/interactions", headers=_auth(token2))
        assert r2.status_code == 404, f"User2 não deveria ver interações: {r2.text}"


# ============================================================================
# 6. CÓDIGO FONTE — verificações estáticas
# ============================================================================

class TestSourceCodeSafety:
    """Verificações estáticas no código-fonte."""

    def test_no_dangerouslysetinnerhtml_in_docs(self):
        """dangerouslySetInnerHTML NÃO deve existir em Docs.tsx (exceto comentários)."""
        import re
        docs_path = backend_dir.parent / "frontend" / "src" / "pages" / "Docs.tsx"
        if docs_path.exists():
            content = docs_path.read_text(encoding="utf-8")
            # Remover comentários antes de verificar
            no_comments = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
            no_comments = re.sub(r'/\*.*?\*/', '', no_comments, flags=re.DOTALL)
            assert "dangerouslySetInnerHTML" not in no_comments, \
                "dangerouslySetInnerHTML encontrado em Docs.tsx — use renderização segura"

    def test_no_empty_catch_in_critical_files(self):
        """Nenhum .catch(() => {}) vazio em arquivos críticos."""
        files = [
            backend_dir.parent / "frontend" / "src" / "pages" / "Onboarding.tsx",
            backend_dir.parent / "frontend" / "src" / "pages" / "AdminDashboard.tsx",
        ]
        for f in files:
            if f.exists():
                content = f.read_text(encoding="utf-8")
                assert ".catch(() => {})" not in content, \
                    f".catch(() => {{}}) encontrado em {f.name}"

    def test_sourcemap_not_true_in_vite_config(self):
        """sourcemap não deve ser true em build de produção."""
        vite_path = backend_dir.parent / "frontend" / "vite.config.ts"
        if vite_path.exists():
            content = vite_path.read_text(encoding="utf-8")
            # Deve ter lógica condicional, não "sourcemap: true" fixo
            assert "sourcemap: true," not in content or "process.env" in content, \
                "sourcemap: true fixo em vite.config.ts"


# ============================================================================
# 7. LIMITES DE QUERY PARAMS
# ============================================================================

class TestQueryLimits:
    """Testa limites de paginação."""

    def test_clients_limit_max_200(self, client):
        token, _ = _create_user_and_token(client, "_qlim")
        r = client.get("/api/crm/clients?limit=999", headers=_auth(token))
        assert r.status_code == 422  # ge=1, le=200

    def test_clients_limit_zero_rejected(self, client):
        token, _ = _create_user_and_token(client, "_ql0")
        r = client.get("/api/crm/clients?limit=0", headers=_auth(token))
        assert r.status_code == 422

    def test_clients_negative_offset_rejected(self, client):
        token, _ = _create_user_and_token(client, "_qo")
        r = client.get("/api/crm/clients?offset=-1", headers=_auth(token))
        assert r.status_code == 422
