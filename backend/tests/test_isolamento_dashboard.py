# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
Isolamento entre tenants no /api/crm/dashboard
===============================================

CONTEXTO — E UMA CORRECAO DE ROTA DE INVESTIGACAO

Em 30/07/2026 eu reportei um "vazamento entre tenants" nesta rota. Estava
ERRADO, e o erro merece registro porque e instrutivo:

  - li a funcao analytics_dashboard (chat_history.py:250), encontrei 7 queries
    sem filtro de user_id;
  - confirmei que a rota /api/crm/dashboard existia e estava registrada;
  - CONCLUI que uma servia a outra, sem verificar o endpoint.

A realidade:

  - /api/crm/dashboard e servida por crm_routes.py:397 -> CRMService.
    get_crm_dashboard(user_id=...), que FILTRA CORRETAMENTE;
  - analytics_dashboard pertence ao analytics_router, que NUNCA e montado —
    e codigo morto (ver AUDITORIA_NEXUS/20_CODIGO_MORTO.md).

Licao: "a rota existe" + "esta funcao tem o defeito" nao prova "a rota expoe o
defeito". So o endpoint registrado decide, e ele se consulta em runtime.

O QUE ESTE TESTE FAZ

Prova que o isolamento REAL funciona, e falha se alguem quebrar. Cria dois
usuarios com dados propositalmente diferentes e verifica que cada um enxerga
somente os seus numeros — nao basta a rota responder 200.

    cd backend && pytest tests/test_isolamento_dashboard.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

MARINA = {"email": "marina-fotografa@teste.com", "password": "Marina1234!"}
JOAO = {"email": "joao-pedreiro@teste.com", "password": "Joao1234!"}

# Valores distintos: se vazar, a soma denuncia.
RECEITA_MARINA = 2500.00
RECEITA_JOAO = 800.00
CLIENTES_MARINA = 3
CLIENTES_JOAO = 1


@pytest.fixture(scope="module")
def app():
    backend = Path(__file__).parent.parent
    sys.path.insert(0, str(backend))
    os.environ.setdefault("JWT_SECRET", "test-secret-isolamento")
    os.environ.setdefault(
        "NEXUS_DB_PATH", str(backend / "data" / "test_isolamento.db"))
    from main import app as _app
    from database.models import init_db
    init_db()
    return _app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


def _registrar(client, dados) -> tuple[str, int]:
    client.post("/api/auth/signup", json={**dados, "full_name": dados["email"]})
    r = client.post("/api/auth/login", json=dados)
    token = r.json()["access_token"]

    from database.models import SessionLocal, User
    db = SessionLocal()
    try:
        uid = db.query(User).filter(User.email == dados["email"]).first().id
    finally:
        db.close()
    return token, uid


@pytest.fixture(scope="module")
def cenario(client):
    from database.models import SessionLocal, Client as ClientModel

    t_marina, id_marina = _registrar(client, MARINA)
    t_joao, id_joao = _registrar(client, JOAO)

    db = SessionLocal()
    try:
        # o .db de teste persiste entre execucoes
        for uid in (id_marina, id_joao):
            db.query(ClientModel).filter(ClientModel.user_id == uid).delete()
        db.commit()

        # revenue.total do dashboard vem de Client.total_revenue
        for uid, qtd, receita in (
            (id_marina, CLIENTES_MARINA, RECEITA_MARINA),
            (id_joao, CLIENTES_JOAO, RECEITA_JOAO),
        ):
            for i in range(qtd):
                db.add(ClientModel(
                    user_id=uid, name=f"cliente-{uid}-{i}",
                    email=f"c{uid}x{i}@teste.com", is_active=True,
                    total_revenue=(receita / qtd),
                ))
        db.commit()
    finally:
        db.close()

    return {"marina": t_marina, "joao": t_joao}


def _dashboard(client, token) -> dict:
    r = client.get("/api/crm/dashboard",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, f"dashboard falhou: {r.status_code} {r.text}"
    return r.json()


# ==========================================================================
# O que importa: os numeros de um nao aparecem para o outro
# ==========================================================================
def test_contagem_de_clientes_isolada(client, cenario):
    d_marina = _dashboard(client, cenario["marina"])
    d_joao = _dashboard(client, cenario["joao"])

    total_marina = d_marina["clients"]["total"]
    total_joao = d_joao["clients"]["total"]

    assert total_marina == CLIENTES_MARINA, (
        f"Marina tem {CLIENTES_MARINA} clientes, dashboard mostrou "
        f"{total_marina}. Se veio {CLIENTES_MARINA + CLIENTES_JOAO}, o filtro "
        "de user_id sumiu do CRMService.")
    assert total_joao == CLIENTES_JOAO, (
        f"Joao tem {CLIENTES_JOAO}, dashboard mostrou {total_joao}")


def test_receita_isolada(client, cenario):
    d_marina = _dashboard(client, cenario["marina"])
    d_joao = _dashboard(client, cenario["joao"])

    rec_marina = float(d_marina["revenue"]["total"] or 0)
    rec_joao = float(d_joao["revenue"]["total"] or 0)

    assert rec_marina == pytest.approx(RECEITA_MARINA, abs=0.01), (
        f"esperado {RECEITA_MARINA}, veio {rec_marina}")
    assert rec_joao == pytest.approx(RECEITA_JOAO, abs=0.01), (
        f"esperado {RECEITA_JOAO}, veio {rec_joao}")


def test_soma_dos_dois_nunca_aparece(client, cenario):
    """Guarda explicita contra o sintoma de vazamento."""
    soma_rec = RECEITA_MARINA + RECEITA_JOAO
    soma_cli = CLIENTES_MARINA + CLIENTES_JOAO

    for quem in ("marina", "joao"):
        d = _dashboard(client, cenario[quem])
        assert float(d["revenue"]["total"] or 0) != pytest.approx(soma_rec, abs=0.01), (
            f"{quem} esta vendo a receita SOMADA dos dois")
        assert d["clients"]["total"] != soma_cli, (
            f"{quem} esta vendo a contagem SOMADA dos dois")


def test_rota_e_servida_pela_funcao_que_isola(app):
    """REGRESSAO da minha propria confusao.

    Se alguem montar o analytics_router (codigo morto, cujo dashboard NAO
    filtra por user_id), esta rota pode passar a ser servida por ele. O teste
    fixa QUEM serve o endpoint, nao so o que ele responde.
    """
    alvo = [r for r in app.routes if getattr(r, "path", "") == "/api/crm/dashboard"]
    assert alvo, "/api/crm/dashboard sumiu"

    fn = alvo[0].endpoint
    assert fn.__module__.endswith("crm_routes"), (
        f"/api/crm/dashboard passou a ser servida por {fn.__module__}."
        f"{fn.__name__} — confirme que essa funcao filtra por user_id antes "
        "de aceitar a mudanca")
