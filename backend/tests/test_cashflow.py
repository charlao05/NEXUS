# pyright: reportMissingImports=false
"""
Testes — Fluxo de Caixa (Visão Diária / Semanal / Range)
==========================================================
Cobertura:
  - get_daily_summary: estrutura, zeros, transações do dia
  - get_weekly_summary: range seg-hoje, isolamento semana anterior
  - get_financial_summary_by_range: somas, by_day, best_day, multi-tenant
  - Endpoints REST: /today, /week, /range
"""

import pytest
from datetime import date, datetime, timedelta
from starlette.testclient import TestClient


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def app():
    """Importa app isolada para testes de cashflow."""
    import sys
    from pathlib import Path
    backend = Path(__file__).parent.parent
    sys.path.insert(0, str(backend))
    import os
    os.environ.setdefault("JWT_SECRET", "test-secret-cashflow")
    os.environ.setdefault("NEXUS_DB_PATH", str(backend / "data" / "test_cashflow.db"))
    os.environ["ADMIN_EMAILS"] = "cashflowadmin@nexus.com"

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
        "email": "cashflowuser@nexus.com",
        "password": "Teste1234!",
        "full_name": "Cashflow User",
    })
    resp = client.post("/api/auth/login", json={
        "email": "cashflowuser@nexus.com",
        "password": "Teste1234!",
    })
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def auth_token_b(client):
    """Segundo usuário para testes de multi-tenancy."""
    client.post("/api/auth/signup", json={
        "email": "cashflowuserB@nexus.com",
        "password": "Teste1234!",
        "full_name": "Cashflow User B",
    })
    resp = client.post("/api/auth/login", json={
        "email": "cashflowuserB@nexus.com",
        "password": "Teste1234!",
    })
    return resp.json()["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def _seed_transactions(client, auth_token):
    """Registra transações de referência para os testes.
    Cria: 2 receitas hoje, 1 despesa hoje, 1 receita ontem (se ainda na mesma semana).
    """
    txs = [
        {"type": "receita", "amount": 500.00, "description": "Venda serviço A", "category": "vendas"},
        {"type": "receita", "amount": 300.00, "description": "Venda serviço B", "category": "vendas"},
        {"type": "despesa", "amount": 120.00, "description": "Material escritório", "category": "material"},
    ]
    for tx in txs:
        resp = client.post("/api/crm/transactions", json=tx, headers=_h(auth_token))
        assert resp.status_code in (200, 201), f"Falha ao criar transação: {resp.text}"
    return True


# ============================================================================
# TESTES — CRMService (unit-style via REST)
# ============================================================================

class TestDailySummary:
    """get_daily_summary / GET /api/crm/financial-summary/today"""

    def test_daily_returns_correct_structure(self, client, auth_token, _seed_transactions):
        """1. get_daily_summary retorna estrutura correta com transações do dia."""
        resp = client.get("/api/crm/financial-summary/today", headers=_h(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        # Campos obrigatórios
        for key in ("start_date", "end_date", "receitas", "despesas", "saldo",
                     "transactions_count", "by_day", "best_day"):
            assert key in data, f"Campo '{key}' ausente"
        assert data["start_date"] == data["end_date"] == date.today().isoformat()

    def test_daily_sums_correct(self, client, auth_token, _seed_transactions):
        """Receitas e despesas do dia somadas corretamente."""
        data = client.get("/api/crm/financial-summary/today", headers=_h(auth_token)).json()
        assert data["receitas"] >= 800.00  # 500 + 300
        assert data["despesas"] >= 120.00
        assert data["transactions_count"] >= 3

    def test_daily_returns_zeros_for_new_user(self, client, auth_token_b):
        """2. get_daily_summary retorna zeros quando não há transações."""
        data = client.get("/api/crm/financial-summary/today", headers=_h(auth_token_b)).json()
        assert data["receitas"] == 0
        assert data["despesas"] == 0
        assert data["saldo"] == 0
        assert data["transactions_count"] == 0
        assert data["best_day"] is None


class TestWeeklySummary:
    """get_weekly_summary / GET /api/crm/financial-summary/week"""

    def test_weekly_includes_today(self, client, auth_token, _seed_transactions):
        """3. get_weekly_summary inclui transações de segunda até hoje."""
        data = client.get("/api/crm/financial-summary/week", headers=_h(auth_token)).json()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        assert data["start_date"] == week_start.isoformat()
        assert data["end_date"] == today.isoformat()
        # As transações criadas hoje devem estar incluídas
        assert data["transactions_count"] >= 3

    def test_weekly_excludes_previous_week(self, client, auth_token):
        """4. get_weekly_summary NÃO inclui transações de semana anterior.
        Verificação indireta: o start_date é segunda-feira da semana atual."""
        data = client.get("/api/crm/financial-summary/week", headers=_h(auth_token)).json()
        start = date.fromisoformat(data["start_date"])
        assert start.weekday() == 0  # 0 = Monday


class TestFinancialSummaryByRange:
    """get_financial_summary_by_range / GET /api/crm/financial-summary/range"""

    def test_receitas_summed(self, client, auth_token, _seed_transactions):
        """5. get_financial_summary_by_range — receitas somadas corretamente."""
        today = date.today().isoformat()
        data = client.get(
            f"/api/crm/financial-summary/range?start={today}&end={today}",
            headers=_h(auth_token),
        ).json()
        assert data["receitas"] >= 800.00

    def test_despesas_summed(self, client, auth_token, _seed_transactions):
        """6. get_financial_summary_by_range — despesas somadas corretamente."""
        today = date.today().isoformat()
        data = client.get(
            f"/api/crm/financial-summary/range?start={today}&end={today}",
            headers=_h(auth_token),
        ).json()
        assert data["despesas"] >= 120.00

    def test_saldo_equals_receitas_minus_despesas(self, client, auth_token, _seed_transactions):
        """7. saldo = receitas - despesas."""
        today = date.today().isoformat()
        data = client.get(
            f"/api/crm/financial-summary/range?start={today}&end={today}",
            headers=_h(auth_token),
        ).json()
        assert data["saldo"] == round(data["receitas"] - data["despesas"], 2)

    def test_by_day_groups_correctly(self, client, auth_token, _seed_transactions):
        """8. by_day agrupa corretamente por data."""
        today = date.today().isoformat()
        data = client.get(
            f"/api/crm/financial-summary/range?start={today}&end={today}",
            headers=_h(auth_token),
        ).json()
        by_day = data["by_day"]
        assert today in by_day
        assert by_day[today]["count"] >= 3
        assert by_day[today]["receitas"] >= 800.00

    def test_best_day_returns_highest_revenue(self, client, auth_token, _seed_transactions):
        """9. best_day retorna o dia com maior receita."""
        today = date.today().isoformat()
        data = client.get(
            f"/api/crm/financial-summary/range?start={today}&end={today}",
            headers=_h(auth_token),
        ).json()
        assert data["best_day"] is not None
        assert data["best_day"]["date"] == today
        assert data["best_day"]["receitas"] >= 800.00

    def test_best_day_none_when_empty(self, client, auth_token_b):
        """10. best_day retorna None quando não há transações."""
        today = date.today().isoformat()
        data = client.get(
            f"/api/crm/financial-summary/range?start={today}&end={today}",
            headers=_h(auth_token_b),
        ).json()
        assert data["best_day"] is None

    def test_user_id_filters_correctly(self, client, auth_token, auth_token_b, _seed_transactions):
        """11. user_id filtra corretamente (multi-tenant)."""
        today = date.today().isoformat()
        data_a = client.get(
            f"/api/crm/financial-summary/range?start={today}&end={today}",
            headers=_h(auth_token),
        ).json()
        data_b = client.get(
            f"/api/crm/financial-summary/range?start={today}&end={today}",
            headers=_h(auth_token_b),
        ).json()
        assert data_a["transactions_count"] >= 3
        assert data_b["transactions_count"] == 0

    def test_single_day_range(self, client, auth_token, _seed_transactions):
        """12. range com start = end retorna apenas 1 dia."""
        today = date.today().isoformat()
        data = client.get(
            f"/api/crm/financial-summary/range?start={today}&end={today}",
            headers=_h(auth_token),
        ).json()
        assert data["start_date"] == data["end_date"] == today
        assert len(data["by_day"]) == 1


class TestCashflowEndpointValidation:
    """Validações extras nos endpoints REST."""

    def test_range_invalid_dates_400(self, client, auth_token):
        """start > end retorna 400."""
        resp = client.get(
            "/api/crm/financial-summary/range?start=2026-12-31&end=2026-01-01",
            headers=_h(auth_token),
        )
        assert resp.status_code == 400

    def test_range_bad_format_400(self, client, auth_token):
        """Formato de data inválido retorna 422 (Pydantic/FastAPI)."""
        resp = client.get(
            "/api/crm/financial-summary/range?start=invalid&end=also-invalid",
            headers=_h(auth_token),
        )
        assert resp.status_code in (400, 422)

    def test_today_no_auth_401(self, client):
        """Sem token retorna 401."""
        resp = client.get("/api/crm/financial-summary/today")
        assert resp.status_code in (401, 403)

    def test_week_no_auth_401(self, client):
        """Sem token retorna 401."""
        resp = client.get("/api/crm/financial-summary/week")
        assert resp.status_code in (401, 403)
