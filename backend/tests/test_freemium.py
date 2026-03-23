"""
test_freemium.py — Teste completo do modelo freemium permanente
================================================================
Valida:
  1. Signup cria usuário com plan=free sem trial_ends_at
  2. Login de usuário free retorna 200 (sem bloqueio)
  3. /me não retorna trial_ends_at
  4. /my-limits retorna limites corretos para cada plano
  5. POST /clients respeita limite de 5 para free
  6. POST /invoices respeita limite de 3/mês para free
  7. Agent execute respeita check_agent_access
  8. Agent execute respeita check_agent_message_limit (10/dia free)
  9. Planos pagos sem restrições de agentes
 10. PLANS endpoint retorna 4 planos + aliases
 11. Resolve_plan mapeia aliases corretamente
"""

import pytest
import sys
import os
import bcrypt
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

# Adicionar root ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from database.models import User, Client, Invoice, ChatMessage, Base, engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_db():
    """Limpa banco antes de cada teste"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def _signup_and_token(client, email="free@test.com", password="Test@12345", plan="free"):
    """Helper: signup via API e retorna token."""
    resp = client.post("/api/auth/signup", json={
        "email": email,
        "password": password,
        "full_name": "Teste",
    })
    assert resp.status_code == 201, f"Signup falhou: {resp.text}"
    token = resp.json()["access_token"]
    # Se precisa de plano diferente, mudar direto no banco
    if plan != "free":
        from database.models import get_session
        db = get_session()
        try:
            user = db.query(User).filter(User.email == email).first()
            user.plan = plan
            db.commit()
        finally:
            db.close()
        # Re-login para obter token com plano atualizado
        resp2 = client.post("/api/auth/login", json={"email": email, "password": password})
        token = resp2.json()["access_token"]
    return token


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Signup cria usuário free sem trial_ends_at
# ---------------------------------------------------------------------------

class TestSignupFreemium:
    def test_signup_creates_free_plan(self, client):
        resp = client.post("/api/auth/signup", json={
            "email": "new_free@test.com",
            "password": "Secure@1234",
            "full_name": "Novo Free",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["plan"] == "free"
        # Não deve retornar trial_ends_at
        assert "trial_ends_at" not in data


# ---------------------------------------------------------------------------
# 2. Login de free retorna 200 (sem bloqueio trial)
# ---------------------------------------------------------------------------

class TestFreeLoginNoBlock:
    def test_free_user_login_ok(self, client):
        _signup_and_token(client, "login_free@test.com")
        resp = client.post("/api/auth/login", json={
            "email": "login_free@test.com",
            "password": "Test@12345",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()


# ---------------------------------------------------------------------------
# 3. /me não retorna trial_ends_at
# ---------------------------------------------------------------------------

class TestMeEndpoint:
    def test_me_no_trial(self, client):
        token = _signup_and_token(client, "me_test@test.com")
        resp = client.get("/api/auth/me", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "free"
        assert "trial_ends_at" not in data


# ---------------------------------------------------------------------------
# 4. /my-limits retorna limites corretos
# ---------------------------------------------------------------------------

class TestMyLimits:
    def test_free_limits(self, client):
        token = _signup_and_token(client, "limits_free@test.com")
        resp = client.get("/api/auth/my-limits", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "free"
        limits = data["limits"]
        assert limits["crm_clients"]["max"] == 5
        assert limits["invoices_per_month"]["max"] == 3
        assert limits["agent_messages_per_day"]["max"] == 10
        assert "contabilidade" in limits["available_agents"]

    def test_profissional_limits(self, client):
        token = _signup_and_token(client, "limits_pro@test.com", plan="profissional")
        resp = client.get("/api/auth/my-limits", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "profissional"
        limits = data["limits"]
        assert limits["crm_clients"]["max"] == 500
        assert limits["agent_messages_per_day"]["max"] == 1000
        assert limits["agent_messages_per_day"]["unlimited"] is False


# ---------------------------------------------------------------------------
# 5. POST /clients respeita limite CRM
# ---------------------------------------------------------------------------

class TestCRMLimit:
    def test_free_crm_limit(self, client):
        token = _signup_and_token(client, "crm_limit@test.com")
        # Criar 5 clientes via API
        for i in range(5):
            resp = client.post(
                "/api/crm/clients",
                json={"name": f"Client {i}", "email": f"c{i}@test.com"},
                headers=_headers(token),
            )
            assert resp.status_code in (200, 201), f"Falhou criando cliente {i}: {resp.text}"

        # O 6° deve ser bloqueado
        resp = client.post(
            "/api/crm/clients",
            json={"name": "Client 6", "email": "c6@test.com"},
            headers=_headers(token),
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["code"] == "LIMIT_REACHED"
        assert detail["resource"] == "crm_clients"


# ---------------------------------------------------------------------------
# 6. POST /invoices respeita limite mensal
# ---------------------------------------------------------------------------

class TestInvoiceLimit:
    def test_free_invoice_limit(self, client):
        token = _signup_and_token(client, "inv_limit@test.com")
        # Primeiro criar um cliente para vincular
        cr = client.post(
            "/api/crm/clients",
            json={"name": "C1", "email": "c1inv@test.com"},
            headers=_headers(token),
        )
        client_id = cr.json().get("id") or cr.json().get("client", {}).get("id")

        # Criar 3 invoices
        for i in range(3):
            resp = client.post(
                "/api/crm/invoices",
                json={"amount": 100.0, "description": f"Invoice {i}", "client_id": client_id, "due_date": "2026-12-31"},
                headers=_headers(token),
            )
            assert resp.status_code in (200, 201), f"Falhou criando invoice {i}: {resp.text}"

        # O 4° deve ser bloqueado
        resp = client.post(
            "/api/crm/invoices",
            json={"amount": 50.0, "description": "Extra", "client_id": client_id, "due_date": "2026-12-31"},
            headers=_headers(token),
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["code"] == "LIMIT_REACHED"
        assert detail["resource"] == "invoices_per_month"


# ---------------------------------------------------------------------------
# 7. Agent access — free só contabilidade
# ---------------------------------------------------------------------------

class TestAgentAccess:
    def test_free_blocked_agent(self, client):
        token = _signup_and_token(client, "agent_acc@test.com")
        # Tentar acessar "assistente" — bloqueado para free
        resp = client.post(
            "/api/agents/assistente/execute",
            json={"action": "chat", "parameters": {"message": "teste"}},
            headers=_headers(token),
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["code"] == "AGENT_NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# 8. Agent message limit (10/dia free)
# ---------------------------------------------------------------------------

class TestAgentMessageLimit:
    def test_free_message_limit(self, client):
        token = _signup_and_token(client, "msg_limit@test.com")
        # Preencher 50 mensagens diretamente no banco
        from database.models import get_session
        db = get_session()
        user = db.query(User).filter(User.email == "msg_limit@test.com").first()
        now = datetime.now(timezone.utc)
        for i in range(50):
            msg = ChatMessage(
                user_id=user.id,
                agent_id="contabilidade",
                role="user",
                content=f"msg {i}",
                created_at=now,
            )
            db.add(msg)
        db.commit()

        resp = client.post(
            "/api/agents/contabilidade/execute",
            json={"action": "chat", "parameters": {"message": "51st message"}},
            headers=_headers(token),
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["code"] == "LIMIT_REACHED"
        assert detail["resource"] == "agent_messages_per_day"


# ---------------------------------------------------------------------------
# 9. Planos pagos sem restrições de agentes
# ---------------------------------------------------------------------------

class TestPaidPlanAccess:
    def test_completo_all_agents(self, client):
        token = _signup_and_token(client, "completo@test.com", plan="completo")
        # Deve poder acessar qualquer agente (não 403)
        resp = client.post(
            "/api/agents/assistente/execute",
            json={"action": "chat", "parameters": {"message": "Olá!"}},
            headers=_headers(token),
        )
        # Não deve ser 403 (pode ser 200 ou 500 se LLM não configurado)
        assert resp.status_code != 403


# ---------------------------------------------------------------------------
# 10. /plans retorna 4 planos + aliases
# ---------------------------------------------------------------------------

class TestPlansEndpoint:
    def test_plans_structure(self, client):
        resp = client.get("/api/auth/plans")
        assert resp.status_code == 200
        data = resp.json()
        # O endpoint retorna PLANS dict diretamente
        assert "free" in data
        assert "essencial" in data
        assert "profissional" in data
        assert "completo" in data
        # Free price = 0
        assert data["free"]["price"] == 0


# ---------------------------------------------------------------------------
# 11. resolve_plan aliases
# ---------------------------------------------------------------------------

class TestResolvePlan:
    def test_aliases(self):
        from app.core.plan_limits import resolve_plan, Plan
        assert resolve_plan("pro") == Plan.ESSENCIAL
        assert resolve_plan("enterprise") == Plan.COMPLETO
        assert resolve_plan("free") == Plan.FREE
        assert resolve_plan("profissional") == Plan.PROFISSIONAL
        # Unknown → FREE
        assert resolve_plan("xyz") == Plan.FREE
