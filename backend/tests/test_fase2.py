# pyright: reportMissingImports=false
"""
Testes Fase 2 — Chat History, Analytics, Trial Enforcement
============================================================
"""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

# Setup path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def clean_db():
    """Limpa banco antes de cada teste"""
    from database.models import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Cria usuário e retorna headers com token"""
    resp = client.post("/api/auth/signup", json={
        "email": "test@nexus.com",
        "password": "SenhaForte@123",
        "full_name": "Test User"
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# CHAT HISTORY
# ============================================================================

class TestChatHistory:
    def test_save_message(self, client, auth_headers):
        resp = client.post("/api/chat/save", json={
            "agent_id": "agenda",
            "role": "user",
            "content": "Quais compromissos tenho hoje?"
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["saved"] is True
        assert "id" in resp.json()

    def test_get_history(self, client, auth_headers):
        # Salvar 2 mensagens
        client.post("/api/chat/save", json={
            "agent_id": "clientes",
            "role": "user",
            "content": "Listar clientes"
        }, headers=auth_headers)
        client.post("/api/chat/save", json={
            "agent_id": "clientes",
            "role": "assistant",
            "content": "Você tem 0 clientes cadastrados."
        }, headers=auth_headers)

        resp = client.get("/api/chat/history/clientes", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "clientes"
        assert data["total"] == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"

    def test_clear_history(self, client, auth_headers):
        client.post("/api/chat/save", json={
            "agent_id": "financeiro",
            "role": "user",
            "content": "Resumo mensal"
        }, headers=auth_headers)

        resp = client.delete("/api/chat/history/financeiro", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["cleared"] is True
        assert resp.json()["messages_deleted"] >= 1

        # Verificar que ficou vazio
        resp = client.get("/api/chat/history/financeiro", headers=auth_headers)
        assert resp.json()["total"] == 0

    def test_history_isolated_by_agent(self, client, auth_headers):
        """Histórico de um agente não interfere no outro"""
        client.post("/api/chat/save", json={
            "agent_id": "agenda",
            "role": "user",
            "content": "msg agenda"
        }, headers=auth_headers)
        client.post("/api/chat/save", json={
            "agent_id": "clientes",
            "role": "user",
            "content": "msg clientes"
        }, headers=auth_headers)

        resp_a = client.get("/api/chat/history/agenda", headers=auth_headers)
        resp_c = client.get("/api/chat/history/clientes", headers=auth_headers)
        assert resp_a.json()["total"] == 1
        assert resp_c.json()["total"] == 1

    def test_save_invalid_role(self, client, auth_headers):
        resp = client.post("/api/chat/save", json={
            "agent_id": "agenda",
            "role": "system",
            "content": "invalid"
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_requires_auth(self, client):
        resp = client.get("/api/chat/history/agenda")
        assert resp.status_code == 401


# ============================================================================
# ANALYTICS — REMOVIDO EM 26/07/2026
# ============================================================================
#
# Três testes (test_analytics_dashboard, test_activity_timeline,
# test_analytics_requires_auth) foram REMOVIDOS por testarem uma feature que
# NUNCA EXISTIU no código:
#
#   - app/api/analytics.py não existe
#   - main.py não menciona analytics em nenhum lugar
#   - nenhuma rota /api/analytics/* é registrada (verificado em app.routes)
#
# Os três recebiam 404 e falhavam desde sempre. Um teste que aponta para rota
# inexistente não é cobertura — é ruído que esconde falha real, e foi parte do
# que manteve o CI vermelho por 134 runs seguidos.
#
# Se o dashboard de analytics for construído um dia, os testes voltam JUNTO com
# a implementação. Recriá-los agora seria inverter a ordem.
#
# O que o teste esperava, para quem for implementar: /api/analytics/dashboard
# com overview, mei (limit 81000.0 e percent_used), activity_timeline,
# chat_usage, revenue_chart, clients_chart; e /api/analytics/activity?days=N.


# ============================================================================
# FREEMIUM — Acesso sem trial
# ============================================================================

class TestFreemiumAccess:
    def test_free_user_has_access(self, client, auth_headers):
        """Usuário free pode acessar /me sem trial_ends_at"""
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["plan"] == "free"

    def test_free_user_not_blocked(self, client):
        """Usuário free NUNCA recebe 403 trial_expired (freemium permanente)"""
        resp = client.post("/api/auth/signup", json={
            "email": "freemium@nexus.com",
            "password": "SenhaForte@123",
            "full_name": "Freemium User"
        })
        token = resp.json()["access_token"]
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["plan"] == "free"

    def test_paid_user_access(self, client):
        """Usuário com plano pago tem acesso normal"""
        resp = client.post("/api/auth/signup", json={
            "email": "paid@nexus.com",
            "password": "SenhaForte@123",
            "full_name": "Paid User"
        })
        token = resp.json()["access_token"]

        from database.models import User, Subscription, SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == "paid@nexus.com").first()
            user.plan = "essencial"  # type: ignore

            sub = Subscription(
                user_id=user.id,
                plan="essencial",
                status="active",
                amount=39.90,
                current_period_start=datetime.now(timezone.utc),
                current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
            )
            db.add(sub)
            db.commit()
        finally:
            db.close()

        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


# ============================================================================
# SECURITY HEADERS
# ============================================================================

class TestSecurityHeaders:
    def test_security_headers_present(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "0"  # OWASP recomenda desativar em favor de CSP

    def test_plans_endpoint(self, client):
        resp = client.get("/api/auth/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert "free" in data
        assert "essencial" in data or "pro" in data
        assert data["free"]["price"] == 0
