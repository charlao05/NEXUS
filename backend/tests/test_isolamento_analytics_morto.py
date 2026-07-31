# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
A ARMADILHA DO analytics_router — desarmada por teste
=====================================================

O QUE E ISTO

`analytics_router` (chat_history.py:22) NUNCA e montado em main.py. E codigo
morto. Mas nao e divida silenciosa — e uma armadilha ARMADA:

  frontend/src/pages/Dashboard.tsx:184 JA chama /api/analytics/dashboard.

Ou seja: a barra de limite MEI, o resultado do mes e os dois graficos nao
aparecem no produto hoje, e o `catch {}` vazio do front engole o 404 em
silencio. Alguem vai "consertar o dashboard" montando o router — e, ate
30/07/2026, isso teria trazido junto DEZ queries sem filtro de user_id,
incluindo a barra dos R$ 81.000 somando o faturamento de todo mundo.

POR QUE ESTE ARQUIVO EXISTE

Rota morta nao se alcanca por HTTP, entao nao da para testa-la pelo app real.
A saida e montar o router num app de teste PROPRIO: o codigo exercitado e
exatamente o mesmo que entraria em producao no dia em que alguem incluir o
`app.include_router(analytics_router)`.

Assim a armadilha fica desarmada de verdade: quem montar o router encontra a
correcao ja coberta, em vez de reintroduzir o vazamento no mesmo commit.

⚠️ Este arquivo NAO monta nada no app de producao. Ver
AUDITORIA_NEXUS/20_CODIGO_MORTO.md para a decisao de montar/apagar.

    cd backend && pytest tests/test_isolamento_analytics_morto.py -v
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

ANA = {"email": "ana-analytics@teste.com", "password": "Ana12345!"}
BRUNO = {"email": "bruno-analytics@teste.com", "password": "Bruno1234!"}

# Valores distintos: se vazar, a soma denuncia.
RECEITA_ANA = 5000.00
RECEITA_BRUNO = 1200.00
DESPESA_ANA = 300.00
CLIENTES_ANA = 2
CLIENTES_BRUNO = 5


@pytest.fixture(scope="module")
def app_producao():
    backend = Path(__file__).parent.parent
    sys.path.insert(0, str(backend))
    os.environ.setdefault("JWT_SECRET", "test-secret-analytics")
    os.environ.setdefault(
        "NEXUS_DB_PATH", str(backend / "data" / "test_analytics_morto.db"))
    from main import app as _app
    from database.models import init_db
    init_db()
    return _app


@pytest.fixture(scope="module")
def app_teste(app_producao):
    """App SO deste teste, com o router morto montado de proposito."""
    from app.api.chat_history import analytics_router

    _app = FastAPI()
    _app.include_router(analytics_router)
    return _app


@pytest.fixture(scope="module")
def client(app_teste):
    return TestClient(app_teste)


@pytest.fixture(scope="module")
def cenario(app_producao):
    """Cria os usuarios pelo app REAL (o de teste nao tem rota de auth)."""
    from database.models import (
        SessionLocal, User, Client as ClientModel, Transaction)

    auth = TestClient(app_producao)
    tokens = {}
    ids = {}
    for apelido, dados in (("ana", ANA), ("bruno", BRUNO)):
        auth.post("/api/auth/signup",
                  json={**dados, "full_name": dados["email"]})
        tokens[apelido] = auth.post(
            "/api/auth/login", json=dados).json()["access_token"]
        db = SessionLocal()
        try:
            ids[apelido] = db.query(User).filter(
                User.email == dados["email"]).first().id
        finally:
            db.close()

    hoje = datetime.now(timezone.utc).date()
    db = SessionLocal()
    try:
        # o .db de teste persiste entre execucoes
        for uid in ids.values():
            db.query(ClientModel).filter(ClientModel.user_id == uid).delete()
            db.query(Transaction).filter(Transaction.user_id == uid).delete()
        db.commit()

        for apelido, qtd in (("ana", CLIENTES_ANA), ("bruno", CLIENTES_BRUNO)):
            for i in range(qtd):
                db.add(ClientModel(
                    user_id=ids[apelido], name=f"c-{apelido}-{i}",
                    email=f"{apelido}{i}@teste.com", is_active=True,
                    created_at=datetime.now(timezone.utc) - timedelta(days=3),
                ))

        db.add(Transaction(user_id=ids["ana"], type="receita",
                           amount=RECEITA_ANA, date=hoje, description="ana"))
        db.add(Transaction(user_id=ids["ana"], type="despesa",
                           amount=DESPESA_ANA, date=hoje, description="ana-d"))
        db.add(Transaction(user_id=ids["bruno"], type="receita",
                           amount=RECEITA_BRUNO, date=hoje, description="bruno"))
        db.commit()
    finally:
        db.close()

    return tokens


def _dash(client, token) -> dict:
    r = client.get("/api/analytics/dashboard",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    return r.json()


# ==========================================================================
# A barra de limite MEI — a query mais sensivel do payload
# ==========================================================================
def test_limite_mei_nao_soma_faturamento_alheio(client, cenario):
    """Se vazar aqui, o usuario ve a propria margem de desenquadramento
    estourada por receita de outro — e pode tomar decisao fiscal errada."""
    d_ana = _dash(client, cenario["ana"])
    d_bruno = _dash(client, cenario["bruno"])

    assert d_ana["mei"]["year_revenue"] == pytest.approx(RECEITA_ANA, abs=0.01), (
        f"esperado {RECEITA_ANA}, veio {d_ana['mei']['year_revenue']} — "
        f"se veio {RECEITA_ANA + RECEITA_BRUNO}, a query 9 voltou a somar tudo")
    assert d_bruno["mei"]["year_revenue"] == pytest.approx(RECEITA_BRUNO, abs=0.01)

    # percent_used e remaining derivam de year_revenue: tem de acompanhar
    assert d_ana["mei"]["remaining"] == pytest.approx(81000.0 - RECEITA_ANA, abs=0.01)


def test_resultado_do_mes_isolado(client, cenario):
    d_ana = _dash(client, cenario["ana"])
    d_bruno = _dash(client, cenario["bruno"])

    assert d_ana["overview"]["month_revenue"] == pytest.approx(RECEITA_ANA, abs=0.01)
    assert d_ana["overview"]["month_expenses"] == pytest.approx(DESPESA_ANA, abs=0.01)
    assert d_ana["overview"]["month_profit"] == pytest.approx(
        RECEITA_ANA - DESPESA_ANA, abs=0.01)

    assert d_bruno["overview"]["month_revenue"] == pytest.approx(RECEITA_BRUNO, abs=0.01)
    assert d_bruno["overview"]["month_expenses"] == pytest.approx(0.0, abs=0.01), (
        "Bruno nao tem despesa; se veio 300, a despesa da Ana vazou")


def test_contagem_de_clientes_isolada(client, cenario):
    d_ana = _dash(client, cenario["ana"])
    d_bruno = _dash(client, cenario["bruno"])

    assert d_ana["overview"]["total_clients"] == CLIENTES_ANA
    assert d_bruno["overview"]["total_clients"] == CLIENTES_BRUNO


def test_graficos_isolados(client, cenario):
    """revenue_chart e clients_chart tambem vazavam — foram os que eu
    esqueci na primeira correcao."""
    d_ana = _dash(client, cenario["ana"])
    d_bruno = _dash(client, cenario["bruno"])

    soma_ana = sum(p["value"] for p in d_ana["revenue_chart"])
    soma_bruno = sum(p["value"] for p in d_bruno["revenue_chart"])
    assert soma_ana == pytest.approx(RECEITA_ANA, abs=0.01)
    assert soma_bruno == pytest.approx(RECEITA_BRUNO, abs=0.01)

    assert sum(p["count"] for p in d_ana["clients_chart"]) == CLIENTES_ANA
    assert sum(p["count"] for p in d_bruno["clients_chart"]) == CLIENTES_BRUNO


def test_soma_dos_dois_nunca_aparece(client, cenario):
    """Guarda explicita contra o sintoma de vazamento."""
    soma_rec = RECEITA_ANA + RECEITA_BRUNO
    soma_cli = CLIENTES_ANA + CLIENTES_BRUNO

    for quem in ("ana", "bruno"):
        d = _dash(client, cenario[quem])
        assert d["mei"]["year_revenue"] != pytest.approx(soma_rec, abs=0.01), (
            f"{quem} ve a receita SOMADA na barra do limite MEI")
        assert d["overview"]["month_revenue"] != pytest.approx(soma_rec, abs=0.01)
        assert d["overview"]["total_clients"] != soma_cli


# ==========================================================================
# Portabilidade: SQLite passa, Postgres (producao) quebrava
# ==========================================================================
def test_clients_chart_nao_usa_funcao_exclusiva_do_sqlite():
    """REGRESSAO de um defeito que teste nenhum pegaria localmente.

    A versao anterior agrupava com func.strftime("%Y-%W", ...), que so existe
    no SQLite. Os testes rodam em SQLite e passariam; producao e Postgres
    (Neon) e levantaria ProgrammingError. Montar o router teria dado 500 na
    rota — depois de o teste ter dito que estava tudo certo.
    """
    import io

    txt = io.open(Path(__file__).parent.parent / "app/api/chat_history.py",
                  encoding="utf-8").read()
    # So o CODIGO conta: o comentario que documenta o defeito cita o nome da
    # funcao de proposito, e nao pode disparar o alarme.
    codigo = [
        linha for linha in txt.splitlines()
        if not linha.lstrip().startswith("#")
    ]
    assert "strftime" not in "\n".join(codigo), (
        "func.strftime e especifica do SQLite. Em Postgres a rota quebra com "
        "500, e a suite local NAO acusa. Agrupe em Python ou use uma funcao "
        "portavel.")
