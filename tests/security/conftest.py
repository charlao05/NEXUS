"""
conftest.py — Fixtures compartilhadas para testes de segurança
================================================================
Cria usuários de teste (free e paid) com tokens JWT válidos,
reutilizando o mesmo padrão de isolamento do backend/tests/conftest.py.
"""

import os
import sys
from pathlib import Path

# ── Isolamento: banco em memória ──
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENVIRONMENT"] = "test"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["NEXUS_SKIP_DOTENV"] = "1"

# Garantir que backend está no PYTHONPATH
backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from database.models import init_db, Base, engine  # noqa: E402

init_db()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    """Recria tabelas antes de cada teste."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client():
    """TestClient para a API NEXUS."""
    from main import app  # noqa: E402
    return TestClient(app)


def _signup_and_get_headers(tc: TestClient, email: str, password: str, full_name: str) -> tuple[dict[str, str], int]:
    """Helper: cria user via signup e retorna (headers, user_id)."""
    resp = tc.post("/api/auth/signup", json={
        "email": email,
        "password": password,
        "full_name": full_name,
    })
    assert resp.status_code == 201, f"Signup falhou: {resp.text}"
    data = resp.json()
    token = data["access_token"]
    user_id = int(data["user_id"])
    return {"Authorization": f"Bearer {token}"}, user_id


@pytest.fixture
def user_a(client: TestClient) -> tuple[dict[str, str], int]:
    """User A — free (padrão)."""
    return _signup_and_get_headers(client, "sectest_a@example.com", "SafePass@123", "User A")


@pytest.fixture
def user_b(client: TestClient) -> tuple[dict[str, str], int]:
    """User B — free (segundo usuário para testes IDOR)."""
    return _signup_and_get_headers(client, "sectest_b@example.com", "SafePass@456", "User B")


@pytest.fixture
def admin_user(client: TestClient) -> tuple[dict[str, str], int]:
    """Admin user (role=admin, plan=profissional)."""
    headers, user_id = _signup_and_get_headers(
        client, "sectest_admin@example.com", "Admin@SecurePass1", "Admin Test"
    )
    # Promove para admin diretamente no banco
    from database.models import SessionLocal, User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.role = "admin"  # type: ignore[assignment]
            user.plan = "profissional"  # type: ignore[assignment]
            db.commit()
    finally:
        db.close()
    return headers, user_id


@pytest.fixture
def free_headers(user_a: tuple[dict[str, str], int]) -> dict[str, str]:
    """Headers de autenticação para user free."""
    return user_a[0]


@pytest.fixture
def admin_headers(admin_user: tuple[dict[str, str], int]) -> dict[str, str]:
    """Headers de autenticação para admin."""
    return admin_user[0]
