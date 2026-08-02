# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
Backup do lado do usuario — `GET /api/auth/export-my-data`
===========================================================

POR QUE ISTO E CRITERIO DE PORTAO A

A frase-objetivo do piloto e literal:

    "Cinco usuarios conseguem trabalhar durante sete dias sem perder dados,
     dinheiro ou confianca."

`sem perder dados` exige resposta. Em 01/08/2026 a varredura mostrou que o
repositorio NAO TEM backup nenhum: sem pg_dump, sem job agendado, nada no
render.yaml. O unico acerto de "backup" no codigo e o agente contabil
ACONSELHANDO o usuario a fazer o dele.

A resposta tem duas metades, e so uma e testavel aqui:

  1. Banco  -> PITR do Neon. Verificacao de painel, do dono. Nao ha codigo
               que prove isso, e fingir que ha seria pior que admitir.
  2. Usuario -> esta rota. Ele leva os proprios dados embora quando quiser.

Este arquivo cobre a metade 2, e trava se ela quebrar.

⚠️ O QUE ESTE TESTE NAO PROVA: que existe backup do BANCO. Se o Neon cair sem
PITR, esta rota nao recupera nada — ela so garante que o usuario tinha como
tirar copia enquanto o sistema estava de pe.

    cd backend && pytest tests/test_backup_exportacao.py -v
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("JWT_SECRET", "test-secret-backup")
os.environ.setdefault("NEXUS_DB_PATH", str(BACKEND / "data" / "test_backup.db"))

DONO = {"email": "dono-backup@teste.com", "password": "Dono12345!"}
ALHEIO = {"email": "alheio-backup@teste.com", "password": "Alheio1234!"}

CLIENTE_DONO = "Barbearia do Ze"
CLIENTE_ALHEIO = "Confeitaria da Rita"


@pytest.fixture(scope="module")
def app():
    from main import app as _app
    from database.models import init_db
    init_db()
    return _app


@pytest.fixture(scope="module")
def cenario(app):
    from starlette.testclient import TestClient
    from database.models import (
        SessionLocal, User, Client as ClientModel, Appointment, Opportunity)
    from app.core.tenant import sem_tenant

    cli = TestClient(app)
    tokens, ids = {}, {}
    for apelido, dados in (("dono", DONO), ("alheio", ALHEIO)):
        cli.post("/api/auth/signup", json={**dados, "full_name": apelido})
        tokens[apelido] = cli.post("/api/auth/login", json=dados).json()["access_token"]

    agora = datetime.now(timezone.utc)
    db = SessionLocal()
    with sem_tenant("carga de dois tenants para o teste de exportacao"):
        try:
            for apelido, dados in (("dono", DONO), ("alheio", ALHEIO)):
                ids[apelido] = db.query(User).filter(
                    User.email == dados["email"]).first().id
            for uid in ids.values():
                db.query(Appointment).filter(Appointment.user_id == uid).delete()
                db.query(ClientModel).filter(ClientModel.user_id == uid).delete()
            db.commit()

            for apelido, nome in (("dono", CLIENTE_DONO), ("alheio", CLIENTE_ALHEIO)):
                uid = ids[apelido]
                c = ClientModel(user_id=uid, name=nome, is_active=True,
                                phone="11988887777")
                db.add(c); db.commit(); db.refresh(c)
                db.add(Appointment(user_id=uid, client_id=c.id,
                                   title=f"Atendimento — {nome}",
                                   scheduled_at=agora + timedelta(days=1),
                                   status="scheduled"))
                db.add(Opportunity(client_id=c.id, title=f"Proposta — {nome}",
                                   value=500.0, stage="proposta"))
            db.commit()
        finally:
            db.close()

    return {"cli": cli, "tokens": tokens, "ids": ids}


def _exportar(cenario, quem: str):
    return cenario["cli"].get(
        "/api/auth/export-my-data",
        headers={"Authorization": f"Bearer {cenario['tokens'][quem]}"})


# ==========================================================================
# 1. O usuario consegue levar os proprios dados
# ==========================================================================
def test_exportacao_responde_e_traz_as_secoes(cenario):
    r = _exportar(cenario, "dono")
    assert r.status_code == 200, f"{r.status_code} — {r.text[:200]}"

    d = r.json()
    for secao in ("profile", "clients", "appointments", "opportunities"):
        assert secao in d, (
            f"a exportacao perdeu a secao '{secao}'. O usuario deixaria de "
            f"levar parte dos proprios dados. Secoes: {sorted(d.keys())}")


def test_exportacao_traz_o_conteudo_real(cenario):
    """Secao vazia com nome certo nao e backup — e a aparencia de um."""
    d = _exportar(cenario, "dono").json()

    nomes = [c.get("name") for c in d["clients"]]
    assert CLIENTE_DONO in nomes, (
        f"o cliente do usuario nao veio na exportacao. clientes: {nomes}")
    assert d["appointments"], "nenhum agendamento exportado"
    assert d["opportunities"], "nenhuma oportunidade exportada"


def test_exportacao_identifica_o_dono(cenario):
    d = _exportar(cenario, "dono").json()
    assert d["profile"].get("email") == DONO["email"]
    assert d.get("export_date"), "faltou a data da exportacao no arquivo"


# ==========================================================================
# 2. Exportacao NAO e porta de vazamento
# ==========================================================================
def test_exportacao_nao_traz_dado_de_outro_usuario(cenario):
    """Uma rota que devolve "todos os meus dados" e o lugar mais tentador para
    um vazamento — e o mais silencioso, porque o payload e grande."""
    import json

    txt = json.dumps(_exportar(cenario, "dono").json(), ensure_ascii=False)
    assert CLIENTE_ALHEIO not in txt, (
        "VAZAMENTO: a exportacao do dono trouxe cliente de outro usuario.")

    txt_alheio = json.dumps(_exportar(cenario, "alheio").json(), ensure_ascii=False)
    assert CLIENTE_DONO not in txt_alheio
    assert DONO["email"] not in txt_alheio


def test_exportacao_exige_autenticacao(cenario):
    r = cenario["cli"].get("/api/auth/export-my-data")
    assert r.status_code in (401, 403), (
        f"exportacao de dados sem autenticacao devolveu {r.status_code}")
