# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
O motor de notificacoes estava DESLIGADO
=========================================

O QUE ACONTECIA ATE 01/08/2026

`_generate_proactive_notifications` (notifications.py:304) tem 6 regras
escritas — boleto do DAS, fatura vencida, vence hoje, vence em 3 dias,
compromisso proximo, lembrete de plano — e NENHUMA chegava ao usuario.

Motivo: so o endpoint SSE `/stream` invocava o gerador, e o frontend nunca
abriu o stream. Ele faz *polling* em `/unread` a cada 30 segundos
(`useNotifications.ts:21,32`), e `/unread` lia apenas uma fila EM MEMORIA que
so o proprio `/stream` populava.

Resultado: o sino do produto exibia praticamente nada. A unica notificacao viva
era "admin recebeu um feedback" (`auth.py:970`) — e era para o admin, nao para
o usuario.

O QUE ESTES TESTES PROVAM

1. O usuario RECEBE as notificacoes proativas (o motor esta ligado).
2. Cada um recebe SO AS SUAS (a pia e o filtro por user_id seguram).
3. O id e ESTAVEL entre consultas — sem isso o front, que deduplica por id,
   mostraria a mesma cobranca duas vezes por minuto, para sempre.

O item 3 e o que decide se a funcionalidade e util ou insuportavel.

    cd backend && pytest tests/test_notificacoes_vivas.py -v
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("JWT_SECRET", "test-secret-notif-vivas")
os.environ.setdefault("NEXUS_DB_PATH", str(BACKEND / "data" / "test_notif_vivas.db"))

ANA = {"email": "ana-notif-viva@teste.com", "password": "Ana12345!"}
BENTO = {"email": "bento-notif-viva@teste.com", "password": "Bento1234!"}

CLIENTE_ANA = "Mercearia da Ana"
CLIENTE_BENTO = "Serralheria do Bento"
VALOR_ANA = 1234.50
VALOR_BENTO = 777.00


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
        SessionLocal, User, Client as ClientModel, Invoice, Appointment)
    from app.core.tenant import sem_tenant

    cli = TestClient(app)
    tokens, ids = {}, {}
    for apelido, dados in (("ana", ANA), ("bento", BENTO)):
        cli.post("/api/auth/signup", json={**dados, "full_name": apelido})
        tokens[apelido] = cli.post("/api/auth/login", json=dados).json()["access_token"]

    agora = datetime.now(timezone.utc)
    hoje = agora.date()
    db = SessionLocal()
    with sem_tenant("carga de dois tenants para o teste"):
        try:
            for apelido, dados in (("ana", ANA), ("bento", BENTO)):
                ids[apelido] = db.query(User).filter(
                    User.email == dados["email"]).first().id

            for uid in ids.values():
                db.query(Invoice).filter(Invoice.user_id == uid).delete()
                db.query(Appointment).filter(Appointment.user_id == uid).delete()
                db.query(ClientModel).filter(ClientModel.user_id == uid).delete()
            db.commit()

            for apelido, nome, valor in (("ana", CLIENTE_ANA, VALOR_ANA),
                                         ("bento", CLIENTE_BENTO, VALOR_BENTO)):
                uid = ids[apelido]
                c = ClientModel(user_id=uid, name=nome, is_active=True)
                db.add(c); db.commit(); db.refresh(c)
                # regra 2 — fatura vencida ha 3 dias
                db.add(Invoice(user_id=uid, client_id=c.id, description="servico",
                               amount=valor, due_date=hoje - timedelta(days=3),
                               status="pending"))
                # regra 1 — compromisso em 1 hora
                db.add(Appointment(user_id=uid, client_id=c.id,
                                   title=f"Visita — {nome}",
                                   scheduled_at=agora + timedelta(hours=1),
                                   status="scheduled"))
            db.commit()
        finally:
            db.close()

    return {"cli": cli, "tokens": tokens, "ids": ids}


def _unread(cenario, quem: str) -> list[dict]:
    r = cenario["cli"].get(
        "/api/notifications/unread",
        headers={"Authorization": f"Bearer {cenario['tokens'][quem]}"})
    assert r.status_code == 200, r.text
    return r.json()["notifications"]


# ==========================================================================
# 1. O MOTOR ESTA LIGADO
# ==========================================================================
def test_usuario_recebe_notificacao_proativa(cenario):
    """Antes desta correcao, esta lista vinha VAZIA para todo mundo."""
    notifs = _unread(cenario, "ana")
    tipos = {n["type"] for n in notifs}

    assert notifs, (
        "nenhuma notificacao chegou ao usuario. O motor voltou a ficar "
        "desligado: /unread deixou de invocar _generate_proactive_notifications.")
    assert "invoice_overdue" in tipos, (
        f"a regra de fatura vencida nao chegou. tipos recebidos: {tipos}")


def test_a_notificacao_carrega_o_dado_util(cenario):
    """Sem nome e valor, o usuario tem de abrir o sistema para descobrir o que
    aconteceu — e a notificacao perde a razao de existir."""
    vencida = [n for n in _unread(cenario, "ana")
               if n["type"] == "invoice_overdue"][0]
    assert CLIENTE_ANA in vencida["message"]
    assert "1.234,50" in vencida["message"] or "1234" in vencida["message"]


# ==========================================================================
# 2. CADA UM RECEBE SO AS SUAS
# ==========================================================================
def test_nao_vaza_entre_usuarios(cenario):
    import json
    txt_ana = json.dumps(_unread(cenario, "ana"), ensure_ascii=False)
    txt_bento = json.dumps(_unread(cenario, "bento"), ensure_ascii=False)

    assert CLIENTE_BENTO not in txt_ana, (
        f"VAZAMENTO: o cliente do Bento apareceu nas notificacoes da Ana")
    assert CLIENTE_ANA not in txt_bento, (
        f"VAZAMENTO: o cliente da Ana apareceu nas notificacoes do Bento")
    assert "777" not in txt_ana, "o valor devido ao Bento vazou para a Ana"


def test_cada_um_ve_o_proprio(cenario):
    """Contraprova: sem ela, os testes acima passariam com a lista vazia."""
    import json
    assert CLIENTE_ANA in json.dumps(_unread(cenario, "ana"), ensure_ascii=False)
    assert CLIENTE_BENTO in json.dumps(_unread(cenario, "bento"), ensure_ascii=False)


# ==========================================================================
# 3. O ID E ESTAVEL — o que decide entre util e insuportavel
# ==========================================================================
def test_id_nao_muda_entre_consultas(cenario):
    """O front consulta a cada 30s e deduplica por id.

    Com o id que o `push` gera (`n-{epoch_ms}`), a MESMA cobranca vencida
    reapareceria duas vezes por minuto, para sempre. O usuario fecharia o
    produto no primeiro dia.
    """
    ids1 = sorted(n["id"] for n in _unread(cenario, "ana"))
    ids2 = sorted(n["id"] for n in _unread(cenario, "ana"))
    ids3 = sorted(n["id"] for n in _unread(cenario, "ana"))

    assert ids1 == ids2 == ids3, (
        "os ids mudaram entre consultas — o front vai acumular a mesma "
        f"notificacao a cada 30 segundos.\n  1: {ids1}\n  2: {ids2}")
    assert all(not i.startswith("n-") for i in ids1), (
        f"id derivado do relogio em vez do conteudo: {ids1}")


def test_notificacao_some_quando_a_condicao_acaba(cenario):
    """Proativa e VISTA DO ESTADO, nao evento.

    Nao se "dispensa" uma fatura vencida — ela some quando e paga. Este teste
    prova essa semantica, que e o que dispensa guardar estado de leitura.
    """
    from database.models import SessionLocal, Invoice
    from app.core.tenant import sem_tenant

    uid = cenario["ids"]["bento"]
    antes = [n for n in _unread(cenario, "bento") if n["type"] == "invoice_overdue"]
    assert antes, "o cenario precisa comecar com fatura vencida"

    db = SessionLocal()
    with sem_tenant("marcar a fatura como paga no teste"):
        try:
            inv = db.query(Invoice).filter(
                Invoice.user_id == uid, Invoice.status == "pending").first()
            inv.status = "paid"
            db.commit()
        finally:
            db.close()

    depois = [n for n in _unread(cenario, "bento") if n["type"] == "invoice_overdue"]
    assert not depois, (
        "a notificacao continuou depois de a fatura ser paga — ela deveria "
        "refletir o estado atual, nao um evento congelado.")
