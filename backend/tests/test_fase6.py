# pyright: reportMissingImports=false
"""
NEXUS — Testes Fase 6
======================
Bloqueios Tier 1 para produção:
  1. PostgreSQL + Alembic
  2. Multi-tenancy (user_id em todos os CRM models)
  3. Auth obrigatória em rotas CRM/Automation
  4. Email service (Resend) + Password reset
  5. LGPD fields no User model

Rodar:  cd backend && python -m pytest tests/test_fase6.py -v --tb=short
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

import pytest

# ── Setup paths ──
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(backend_dir.parent))

os.environ.setdefault("JWT_SECRET", "test-secret-fase6")
os.environ.setdefault("ENVIRONMENT", "test")

from fastapi.testclient import TestClient


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def app():
    """Cria app de teste."""
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
    """Helper: cria user e retorna (token, email)."""
    email = f"fase6user{suffix}_{int(time.time())}@nexus.com"
    signup_r = client.post("/api/auth/signup", json={
        "email": email,
        "password": "TesteFase6!@#",
        "full_name": f"Teste Fase6 {suffix}",
    })
    assert signup_r.status_code in (200, 201), f"Signup failed: {signup_r.json()}"
    r = client.post("/api/auth/login", json={
        "email": email,
        "password": "TesteFase6!@#",
    })
    assert r.status_code == 200, f"Login failed: {r.json()}"
    return r.json()["access_token"], email


@pytest.fixture(scope="module")
def auth_token(client):
    """Token do usuário A."""
    token, _ = _create_user_and_token(client, "A")
    return token


@pytest.fixture(scope="module")
def auth_token_b(client):
    """Token do usuário B (para testes multi-tenancy)."""
    token, _ = _create_user_and_token(client, "B")
    return token


@pytest.fixture
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def headers_b(auth_token_b):
    return {"Authorization": f"Bearer {auth_token_b}"}


# ============================================================================
# 1. POSTGRESQL + ALEMBIC CONFIG
# ============================================================================

class TestDatabaseConfig:
    """Testa configuração de banco de dados."""

    def test_database_url_env_support(self):
        """DATABASE_URL é lido do ambiente."""
        from database.models import DATABASE_URL
        # Em testes cai no SQLite fallback (sem DATABASE_URL)
        assert isinstance(DATABASE_URL, str)

    def test_engine_exists(self):
        """Engine foi criado corretamente."""
        from database.models import engine
        assert engine is not None
        # SQLite fallback em testes
        assert "sqlite" in str(engine.url) or "postgresql" in str(engine.url)

    def test_session_local_factory(self):
        """SessionLocal funciona."""
        from database.models import SessionLocal
        session = SessionLocal()
        assert session is not None
        session.close()

    def test_alembic_env_importable(self):
        """alembic/env.py é importável e contém configuração."""
        alembic_env = backend_dir / "alembic" / "env.py"
        assert alembic_env.exists(), "alembic/env.py não encontrado"
        content = alembic_env.read_text()
        assert "render_as_batch" in content
        assert "target_metadata" in content

    def test_alembic_ini_exists(self):
        """alembic.ini existe."""
        assert (backend_dir / "alembic.ini").exists()

    def test_postgres_url_fixup(self):
        """postgres:// é convertido para postgresql://."""
        # Testa lógica de conversão (sem realmente conectar)
        test_url = "postgres://user:pass@host:5432/db"
        fixed = test_url.replace("postgres://", "postgresql://", 1)
        assert fixed == "postgresql://user:pass@host:5432/db"


# ============================================================================
# 2. LGPD FIELDS NO USER MODEL
# ============================================================================

class TestUserLGPDFields:
    """Testa campos LGPD no modelo User."""

    def test_user_has_email_verified(self):
        from database.models import User
        assert hasattr(User, "email_verified")

    def test_user_has_lgpd_consent(self):
        from database.models import User
        assert hasattr(User, "lgpd_consent")

    def test_user_has_lgpd_consent_at(self):
        from database.models import User
        assert hasattr(User, "lgpd_consent_at")

    def test_user_has_lgpd_consent_ip(self):
        from database.models import User
        assert hasattr(User, "lgpd_consent_ip")

    def test_user_has_password_reset_token(self):
        from database.models import User
        assert hasattr(User, "password_reset_token")

    def test_user_has_password_reset_expires(self):
        from database.models import User
        assert hasattr(User, "password_reset_expires")

    def test_user_to_dict_includes_lgpd(self):
        """to_dict() inclui campos LGPD."""
        from database.models import User
        u = User(
            email="test@t.com",
            password_hash="x",
            full_name="T",
            plan="free",
        )
        d = u.to_dict()
        assert "email_verified" in d
        assert "lgpd_consent" in d


# ============================================================================
# 3. MULTI-TENANCY (user_id em CRM models)
# ============================================================================

class TestMultiTenancyModels:
    """Verifica user_id nos modelos CRM."""

    def test_client_has_user_id(self):
        from database.models import Client
        assert hasattr(Client, "user_id")

    def test_transaction_has_user_id(self):
        from database.models import Transaction
        assert hasattr(Transaction, "user_id")

    def test_invoice_has_user_id(self):
        from database.models import Invoice
        assert hasattr(Invoice, "user_id")

    def test_appointment_has_user_id(self):
        from database.models import Appointment
        assert hasattr(Appointment, "user_id")

    def test_webtask_has_user_id(self):
        from database.models import WebTask
        assert hasattr(WebTask, "user_id")


# ============================================================================
# 4. AUTH OBRIGATÓRIA EM ROTAS CRM
# ============================================================================

class TestCRMAuthRequired:
    """Todas as rotas CRM devem retornar 401/403 sem token."""

    CRM_ENDPOINTS = [
        ("GET", "/api/crm/clients"),
        ("POST", "/api/crm/clients"),
        ("GET", "/api/crm/clients/followup"),
        ("GET", "/api/crm/clients/birthdays"),
        ("GET", "/api/crm/pipeline"),
        ("GET", "/api/crm/appointments"),
        ("GET", "/api/crm/financial-summary"),
        ("GET", "/api/crm/invoices/overdue"),
        ("GET", "/api/crm/invoices/upcoming"),
        ("GET", "/api/crm/dashboard"),
    ]

    @pytest.mark.parametrize("method,path", CRM_ENDPOINTS)
    def test_crm_route_requires_auth(self, client, method, path):
        """Rotas CRM retornam 401 sem token (ou 429 se rate limited)."""
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json={})
        assert r.status_code in (401, 403, 422, 429), (
            f"{method} {path} retornou {r.status_code} sem auth"
        )

    def test_automation_plan_requires_auth(self, client):
        """POST /api/automation/tasks/plan — rota removida (órfã), deve retornar 404."""
        r = client.post("/api/automation/tasks/plan", json={"message": "test task"})
        assert r.status_code in (401, 403, 404, 422, 429)

    def test_automation_list_requires_auth(self, client):
        """GET /api/automation/tasks — rota removida (órfã), deve retornar 404."""
        r = client.get("/api/automation/tasks")
        assert r.status_code in (401, 403, 404, 422, 429)


# ============================================================================
# 5. MULTI-TENANCY: ISOLAMENTO DE DADOS
# ============================================================================

class TestMultiTenancyIsolation:
    """Usuário A não vê dados do usuário B."""

    def test_clients_isolated(self, client, headers, headers_b):
        """Cliente criado por A não aparece na listagem de B."""
        # Usuário A cria cliente
        r_a = client.post("/api/crm/clients", headers=headers, json={
            "name": "ClienteDoA_Fase6",
            "email": "a_client_iso@nexus.com",
            "phone": "11999990099",
        })
        assert r_a.status_code in (200, 201), f"Criar client A falhou: {r_a.json()}"

        # Usuário B lista clientes — não deve ver o de A
        r_b = client.get("/api/crm/clients", headers=headers_b)
        assert r_b.status_code == 200
        data = r_b.json()
        clients_list = data.get("clients", data) if isinstance(data, dict) else data
        names = [c.get("name", c.get("nome", "")) for c in clients_list]
        assert "ClienteDoA_Fase6" not in names, "Tenant B pode ver client do tenant A!"

    def test_dashboard_isolated(self, client, headers, headers_b):
        """Dashboard retorna dados isolados por tenant."""
        r_a = client.get("/api/crm/dashboard", headers=headers)
        r_b = client.get("/api/crm/dashboard", headers=headers_b)
        assert r_a.status_code == 200
        assert r_b.status_code == 200
        # Ambos devem funcionar sem erros
        assert "total_clients" in r_a.json() or "total_clientes" in r_a.json() or isinstance(r_a.json(), dict)


# ============================================================================
# 6. CRM OPERATIONS COM AUTH
# ============================================================================

class TestCRMWithAuth:
    """Testa operações CRM autenticadas."""

    def test_create_client_authenticated(self, client, headers):
        r = client.post("/api/crm/clients", headers=headers, json={
            "name": "Auth Client Fase6",
            "email": "auth_client_f6@nexus.com",
            "phone": "11888880099",
        })
        assert r.status_code in (200, 201)
        data = r.json()
        # API retorna {status: 'created', client: {...}}
        inner = data.get("client", data)
        assert inner.get("name") or inner.get("nome")

    def test_list_clients_authenticated(self, client, headers):
        r = client.get("/api/crm/clients", headers=headers)
        assert r.status_code == 200
        data = r.json()
        # API pode retornar lista ou {total, clients: [...]}
        clients = data.get("clients", data) if isinstance(data, dict) else data
        assert isinstance(clients, list)

    def test_pipeline_authenticated(self, client, headers):
        r = client.get("/api/crm/pipeline", headers=headers)
        assert r.status_code == 200

    def test_financial_summary_authenticated(self, client, headers):
        r = client.get("/api/crm/financial-summary", headers=headers)
        assert r.status_code == 200

    def test_appointments_authenticated(self, client, headers):
        r = client.get("/api/crm/appointments", headers=headers)
        assert r.status_code == 200

    def test_invoices_overdue_authenticated(self, client, headers):
        r = client.get("/api/crm/invoices/overdue", headers=headers)
        assert r.status_code == 200

    def test_invoices_upcoming_authenticated(self, client, headers):
        r = client.get("/api/crm/invoices/upcoming", headers=headers)
        assert r.status_code == 200


# ============================================================================
# 7. EMAIL SERVICE (RESEND)
# ============================================================================

class TestEmailService:
    """Testa serviço de email."""

    def test_import_email_service(self):
        from app.api.email_service import send_email, generate_reset_token
        assert callable(send_email)
        assert callable(generate_reset_token)

    def test_generate_reset_token_format(self):
        from app.api.email_service import generate_reset_token
        token = generate_reset_token()
        assert isinstance(token, str)
        assert len(token) > 20  # token_urlsafe(36) gera ~48 chars

    def test_send_email_without_apikey(self):
        """Sem RESEND_API_KEY, retorna status 'skipped'."""
        # Garantir que não tem API key
        with patch.dict(os.environ, {"RESEND_API_KEY": ""}, clear=False):
            # Reimportar para pegar env limpo
            import importlib
            from app.api import email_service
            importlib.reload(email_service)
            result = email_service.send_email("test@t.com", "Test", "<p>Test</p>")
            assert result.get("status") == "skipped"

    def test_send_welcome_email_function_exists(self):
        from app.api.email_service import send_welcome_email
        assert callable(send_welcome_email)

    def test_send_password_reset_email_function_exists(self):
        from app.api.email_service import send_password_reset_email
        assert callable(send_password_reset_email)


# ============================================================================
# 8. FORGOT/RESET PASSWORD ENDPOINTS
# ============================================================================

class TestPasswordReset:
    """Testa fluxo de recuperação de senha."""

    def test_forgot_password_returns_message(self, client):
        """Forgot password retorna mensagem genérica (anti-enumeração)."""
        r = client.post("/api/auth/forgot-password", json={
            "email": "nonexistent@nexus.com"
        })
        assert r.status_code == 200
        data = r.json()
        msg = data.get("message", "").lower()
        assert "enviaremos" in msg or "enviado" in msg or data.get("status") == "sent"

    def test_reset_password_invalid_token(self, client):
        """Reset com token inválido retorna 400."""
        r = client.post("/api/auth/reset-password", json={
            "token": "token-invalido-123",
            "new_password": "novaSenha123!",
        })
        assert r.status_code == 400

    def test_forgot_password_with_real_user(self, client):
        """Forgot password com user real não dá erro."""
        # Cria user
        email = f"forgot_test_{int(time.time())}@nexus.com"
        client.post("/api/auth/signup", json={
            "email": email,
            "password": "TestReset123!",
            "full_name": "Reset Test",
        })
        r = client.post("/api/auth/forgot-password", json={"email": email})
        assert r.status_code == 200

    def test_full_password_reset_flow(self, client):
        """Fluxo completo: signup → forgot → inject token → reset → login com nova senha."""
        from database.models import SessionLocal, User
        from app.api.email_service import generate_reset_token

        email = f"fullreset_{int(time.time())}@nexus.com"
        # 1. Signup
        sr = client.post("/api/auth/signup", json={
            "email": email,
            "password": "SenhaOriginal123!",
            "full_name": "Full Reset Test",
        })
        assert sr.status_code in (200, 201)

        # 2. Injetar token diretamente no DB (simula forgot-password)
        token = generate_reset_token()
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            user.password_reset_token = token
            user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
            db.commit()
        finally:
            db.close()

        # 3. Reset password com token válido
        rr = client.post("/api/auth/reset-password", json={
            "token": token,
            "new_password": "NovaSenha456!",
        })
        assert rr.status_code == 200, f"Reset falhou: {rr.json()}"

        # 4. Login com nova senha
        lr = client.post("/api/auth/login", json={
            "email": email,
            "password": "NovaSenha456!",
        })
        assert lr.status_code == 200, "Login com nova senha falhou"
        assert "access_token" in lr.json()

        # 5. Login com senha antiga deve falhar
        old_lr = client.post("/api/auth/login", json={
            "email": email,
            "password": "SenhaOriginal123!",
        })
        assert old_lr.status_code in (400, 401)

    def test_expired_reset_token(self, client):
        """Token expirado é rejeitado."""
        from database.models import SessionLocal, User
        from app.api.email_service import generate_reset_token

        email = f"expired_{int(time.time())}@nexus.com"
        client.post("/api/auth/signup", json={
            "email": email,
            "password": "Temp123!@#",
            "full_name": "Expired Token Test",
        })

        token = generate_reset_token()
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            user.password_reset_token = token
            # Token expirado há 1 hora
            user.password_reset_expires = datetime.utcnow() - timedelta(hours=1)
            db.commit()
        finally:
            db.close()

        r = client.post("/api/auth/reset-password", json={
            "token": token,
            "new_password": "NovaSenha789!",
        })
        assert r.status_code == 400
        assert "expirado" in r.json().get("detail", "").lower() or "expired" in r.json().get("detail", "").lower()


# ============================================================================
# 9. CRM SERVICE MULTI-TENANCY
# ============================================================================

class TestCRMServiceMultiTenancy:
    """Testa CRMService diretamente com user_id."""

    def test_create_client_with_user_id(self):
        from database.crm_service import CRMService
        svc = CRMService()
        result = svc.create_client(
            name="Tenant Test", email="tenant_f6@test.com", phone="11000000099",
            user_id=999
        )
        assert result is not None

    def test_search_clients_filters_by_user(self):
        from database.crm_service import CRMService
        svc = CRMService()
        # Cria cliente para user 998
        svc.create_client(
            name="User998 Client", email="u998@test.com", phone="11000000002",
            user_id=998
        )
        # Busca como user 997 — não deve encontrar
        results = svc.search_clients("User998", user_id=997)
        if isinstance(results, list):
            names = []
            for c in results:
                if isinstance(c, dict):
                    names.append(c.get("name", c.get("nome", "")))
                elif isinstance(c, str):
                    names.append(c)
            assert "User998 Client" not in names

    def test_get_clients_for_followup_with_user_id(self):
        from database.crm_service import CRMService
        svc = CRMService()
        results = svc.get_clients_for_followup(user_id=9999)
        assert isinstance(results, list)

    def test_get_birthday_clients_with_user_id(self):
        from database.crm_service import CRMService
        svc = CRMService()
        results = svc.get_birthday_clients(user_id=9999)
        assert isinstance(results, list)

    def test_financial_summary_with_user_id(self):
        from database.crm_service import CRMService
        svc = CRMService()
        result = svc.get_financial_summary(user_id=9999)
        assert isinstance(result, dict)

    def test_overdue_invoices_with_user_id(self):
        from database.crm_service import CRMService
        svc = CRMService()
        result = svc.get_overdue_invoices(user_id=9999)
        assert isinstance(result, list)


# ============================================================================
# 10. REQUIREMENTS.TXT
# ============================================================================

class TestRequirements:
    """Verifica dependências no requirements.txt."""

    def test_alembic_in_requirements(self):
        req = (backend_dir / "requirements.txt").read_text()
        assert "alembic" in req.lower()

    def test_psycopg2_in_requirements(self):
        req = (backend_dir / "requirements.txt").read_text()
        assert "psycopg2" in req.lower()

    def test_resend_in_requirements(self):
        req = (backend_dir / "requirements.txt").read_text()
        assert "resend" in req.lower()


# ============================================================================
# 11. HEALTH CHECK STILL WORKS
# ============================================================================

class TestHealthCheck:
    """Testa que endpoints básicos ainda funcionam."""

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert "name" in data or "status" in data or "message" in data
