# pyright: reportMissingImports=false
"""
NEXUS — Testes de Autenticação (pytest)
========================================
Testa signup, login, auth inválida, /me, e email duplicado.

Rodar: cd backend && python -m pytest tests/ -v
"""

import sys
from pathlib import Path

# Ensure backend is in path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient
from database.models import Base, engine, SessionLocal, User  # type: ignore[import]
from main import app  # type: ignore[import]


@pytest.fixture(autouse=True)
def clean_db():
    """Recria tabelas antes de cada teste"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# SIGNUP
# ============================================================================

class TestSignup:
    def test_signup_success(self, client: TestClient):
        resp = client.post("/api/auth/signup", json={
            "email": "teste@nexus.com",
            "password": "Senha@123",
            "full_name": "Teste NEXUS",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "teste@nexus.com"
        assert data["plan"] == "free"
        assert "access_token" in data
        assert len(data["access_token"]) > 20

    def test_signup_duplicate_email(self, client: TestClient):
        payload = {
            "email": "dup@nexus.com",
            "password": "Senha@123",
            "full_name": "Dup User",
        }
        resp1 = client.post("/api/auth/signup", json=payload)
        assert resp1.status_code == 201

        resp2 = client.post("/api/auth/signup", json=payload)
        assert resp2.status_code == 400
        assert "já cadastrado" in resp2.json()["detail"]

    def test_signup_short_password(self, client: TestClient):
        resp = client.post("/api/auth/signup", json={
            "email": "short@nexus.com",
            "password": "123",
            "full_name": "Short Pwd",
        })
        assert resp.status_code == 400
        assert "8 caracteres" in resp.json()["detail"]

    def test_signup_invalid_email(self, client: TestClient):
        resp = client.post("/api/auth/signup", json={
            "email": "not-an-email",
            "password": "Senha@123",
            "full_name": "Bad Email",
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_signup_saves_to_db(self, client: TestClient):
        client.post("/api/auth/signup", json={
            "email": "db@nexus.com",
            "password": "Senha@123",
            "full_name": "DB Test",
        })
        db = SessionLocal()
        user = db.query(User).filter(User.email == "db@nexus.com").first()
        db.close()
        assert user is not None
        assert user.full_name == "DB Test"
        assert user.plan == "free"
        assert user.password_hash != "Senha@123"  # Deve ser hash, não plaintext


# ============================================================================
# LOGIN
# ============================================================================

class TestLogin:
    def _create_user(self, client: TestClient):
        client.post("/api/auth/signup", json={
            "email": "login@nexus.com",
            "password": "Senha@123",
            "full_name": "Login User",
        })

    def test_login_success(self, client: TestClient):
        self._create_user(client)
        resp = client.post("/api/auth/login", json={
            "email": "login@nexus.com",
            "password": "Senha@123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "login@nexus.com"
        assert "access_token" in data

    def test_login_wrong_password(self, client: TestClient):
        self._create_user(client)
        resp = client.post("/api/auth/login", json={
            "email": "login@nexus.com",
            "password": "senha_errada",
        })
        assert resp.status_code == 401
        assert "inválidos" in resp.json()["detail"]

    def test_login_nonexistent_email(self, client: TestClient):
        resp = client.post("/api/auth/login", json={
            "email": "naoexiste@nexus.com",
            "password": "qualquer",
        })
        assert resp.status_code == 401

    def test_login_updates_last_login(self, client: TestClient):
        self._create_user(client)
        client.post("/api/auth/login", json={
            "email": "login@nexus.com",
            "password": "Senha@123",
        })
        db = SessionLocal()
        user = db.query(User).filter(User.email == "login@nexus.com").first()
        db.close()
        assert user is not None
        assert user.last_login is not None


# ============================================================================
# /ME — Profile endpoint
# ============================================================================

class TestProfile:
    def _get_token(self, client: TestClient) -> str:
        resp = client.post("/api/auth/signup", json={
            "email": "me@nexus.com",
            "password": "Senha@123",
            "full_name": "Me User",
        })
        return resp.json()["access_token"]

    def test_me_authenticated(self, client: TestClient):
        token = self._get_token(client)
        resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@nexus.com"
        assert data["full_name"] == "Me User"
        assert data["plan"] == "free"
        assert data["requests_limit"] == 100

    def test_me_no_token(self, client: TestClient):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client: TestClient):
        resp = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid.token.here",
        })
        assert resp.status_code == 401


# ============================================================================
# CRM — Verifica que endpoints CRM existem
# ============================================================================

class TestCRM:
    def test_health(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_crm_dashboard(self, client: TestClient):
        # CRM dashboard agora requer auth (Fase 6 multi-tenancy)
        # Sem token, espera 401
        resp_no_auth = client.get("/api/crm/dashboard")
        assert resp_no_auth.status_code in (401, 403, 429)

        # Com auth, deve funcionar
        signup = client.post("/api/auth/signup", json={
            "email": "crm_dash@nexus.com",
            "password": "Senha@123",
            "full_name": "CRM Dash Test",
        })
        assert signup.status_code in (200, 201)
        login_r = client.post("/api/auth/login", json={
            "email": "crm_dash@nexus.com",
            "password": "Senha@123",
        })
        token = login_r.json()["access_token"]
        resp = client.get("/api/crm/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "clients" in data or "total_clients" in data or isinstance(data, dict)
