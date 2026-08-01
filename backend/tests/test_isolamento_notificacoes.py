# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
Isolamento entre tenants no motor de notificacoes proativas
============================================================

O DEFEITO (encontrado e corrigido em 01/08/2026 — E-041)

`_generate_proactive_notifications` (notifications.py:304) tem 6 regras. QUATRO
delas nao filtravam por user_id e varriam a tabela inteira:

  regra 1  agendamentos nas proximas 2h  -> titulo do compromisso alheio
  regra 2  faturas vencidas              -> NOME DO CLIENTE + VALOR DEVIDO
  regra 3  faturas vencendo hoje         -> idem
  regra 4  faturas vencendo em 3 dias    -> idem

ALCANCE NA EPOCA: o router ESTA montado, entao GET /api/notifications/stream
(:210) servia dado alheio a qualquer autenticado que a chamasse. O frontend nao
abria o stream (so faz polling em /unread, que le uma fila em memoria populada
pelo proprio stream), entao nao vazava pela UI — mas bastava alguem ligar o
stream para virar vazamento pleno.

POR QUE ISTO E CLASSE A

Nao e defeito de produto, e defeito de confidencialidade. Uma notificacao que
diz "Joao Pedreiro — R$ 1.850,00 venceu ha 3 dias" para a Marina nao e um bug
de UI: e a confianca indo embora num unico evento.

O QUE ESTES TESTES PROVAM

Que NENHUMA das 6 regras devolve nome, valor, titulo de compromisso ou
identificador pertencente a outro usuario. E, principalmente, que eles FALHAM
se alguem remover qualquer filtro — verificado por mutacao.

    cd backend && pytest tests/test_isolamento_notificacoes.py -v
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("JWT_SECRET", "test-secret-notif")
os.environ.setdefault("NEXUS_DB_PATH", str(BACKEND / "data" / "test_notif.db"))

# Dados propositalmente distintos: se vazar, o valor do outro denuncia.
MARINA_CLIENTE = "Joao Pedreiro"
MARINA_VALOR = 1850.00
MARINA_COMPROMISSO = "Ensaio fotografico da Beatriz"

LUCAS_CLIENTE = "Padaria do Lucas"
LUCAS_VALOR = 320.00
LUCAS_COMPROMISSO = "Entrega de encomenda"


@pytest.fixture(scope="module")
def cenario():
    """Dois usuarios, cada um com fatura vencida e compromisso proximo."""
    from database.models import (
        init_db, SessionLocal, User, Client, Invoice, Appointment)
    init_db()

    db = SessionLocal()
    try:
        ids = {}
        for apelido, email in (("marina", "marina-notif@teste.com"),
                               ("lucas", "lucas-notif@teste.com")):
            u = db.query(User).filter(User.email == email).first()
            if not u:
                u = User(email=email, full_name=apelido, password_hash="x",
                         plan="completo")
                db.add(u)
                db.commit()
                db.refresh(u)
            ids[apelido] = u.id

        # o .db de teste persiste entre execucoes
        for uid in ids.values():
            db.query(Invoice).filter(Invoice.user_id == uid).delete()
            db.query(Appointment).filter(Appointment.user_id == uid).delete()
            db.query(Client).filter(Client.user_id == uid).delete()
        db.commit()

        agora = datetime.now(timezone.utc)
        hoje = agora.date()

        for apelido, nome_cli, valor, compromisso in (
            ("marina", MARINA_CLIENTE, MARINA_VALOR, MARINA_COMPROMISSO),
            ("lucas", LUCAS_CLIENTE, LUCAS_VALOR, LUCAS_COMPROMISSO),
        ):
            uid = ids[apelido]
            c = Client(user_id=uid, name=nome_cli, is_active=True)
            db.add(c)
            db.commit()
            db.refresh(c)

            # regra 2 — vencida ha 3 dias
            db.add(Invoice(user_id=uid, client_id=c.id, description="servico",
                           amount=valor, due_date=hoje - timedelta(days=3),
                           status="pending"))
            # regra 3 — vence hoje
            db.add(Invoice(user_id=uid, client_id=c.id, description="servico",
                           amount=valor, due_date=hoje, status="pending"))
            # regra 4 — vence em 2 dias
            db.add(Invoice(user_id=uid, client_id=c.id, description="servico",
                           amount=valor, due_date=hoje + timedelta(days=2),
                           status="pending"))
            # regra 1 — compromisso em 1 hora
            db.add(Appointment(user_id=uid, client_id=c.id, title=compromisso,
                               scheduled_at=agora + timedelta(hours=1),
                               status="scheduled"))
        db.commit()
        return ids
    finally:
        db.close()


def _notificacoes(user_id: int) -> list[dict]:
    from app.api.notifications import _generate_proactive_notifications
    return _generate_proactive_notifications(user_id)


def _texto(notifs: list[dict]) -> str:
    """Tudo que a notificacao carrega — titulo, mensagem E o payload data."""
    import json
    return json.dumps(notifs, ensure_ascii=False, default=str)


# ==========================================================================
# A prova central: o dado do outro NUNCA aparece
# ==========================================================================
def test_marina_nao_ve_nada_do_lucas(cenario):
    txt = _texto(_notificacoes(cenario["marina"]))

    assert LUCAS_CLIENTE not in txt, (
        f"VAZAMENTO: o nome do cliente do Lucas ('{LUCAS_CLIENTE}') apareceu "
        "nas notificacoes da Marina.")
    assert f"{LUCAS_VALOR:,.2f}" not in txt, (
        f"VAZAMENTO: o valor devido ao Lucas (R$ {LUCAS_VALOR}) apareceu "
        "nas notificacoes da Marina.")
    assert LUCAS_COMPROMISSO not in txt, (
        "VAZAMENTO: o compromisso do Lucas apareceu na agenda da Marina.")


def test_lucas_nao_ve_nada_da_marina(cenario):
    txt = _texto(_notificacoes(cenario["lucas"]))

    assert MARINA_CLIENTE not in txt, (
        f"VAZAMENTO: '{MARINA_CLIENTE}' (cliente da Marina) apareceu para o Lucas.")
    assert f"{MARINA_VALOR:,.2f}" not in txt, (
        "VAZAMENTO: o valor devido a Marina apareceu para o Lucas.")
    assert MARINA_COMPROMISSO not in txt, (
        "VAZAMENTO: o compromisso da Marina apareceu para o Lucas.")


def test_cada_um_ve_os_proprios(cenario):
    """Contraprova: se o filtro fosse forte demais, ninguem veria nada — e os
    testes acima passariam sem provar coisa alguma."""
    txt_marina = _texto(_notificacoes(cenario["marina"]))
    txt_lucas = _texto(_notificacoes(cenario["lucas"]))

    assert MARINA_CLIENTE in txt_marina, (
        "Marina deixou de ver o proprio cliente — o filtro quebrou a funcao")
    assert MARINA_COMPROMISSO in txt_marina
    assert LUCAS_CLIENTE in txt_lucas
    assert LUCAS_COMPROMISSO in txt_lucas


def test_contagem_por_regra_nao_soma_os_dois(cenario):
    """Guarda contra o sintoma: cada um tem 3 faturas e 1 compromisso.
    Se vazar, viram 6 e 2."""
    notifs = _notificacoes(cenario["marina"])
    tipos = [n["type"] for n in notifs]

    assert tipos.count("invoice_overdue") == 1, (
        f"esperado 1 fatura vencida, veio {tipos.count('invoice_overdue')} — "
        "se veio 2, a regra 2 voltou a somar os dois tenants")
    assert tipos.count("invoice_due_today") == 1, (
        f"esperado 1 vencendo hoje, veio {tipos.count('invoice_due_today')}")
    assert tipos.count("invoice_due_soon") == 1, (
        f"esperado 1 vencendo em breve, veio {tipos.count('invoice_due_soon')}")
    assert tipos.count("appointment_reminder") == 1, (
        f"esperado 1 compromisso, veio {tipos.count('appointment_reminder')}")


# ==========================================================================
# REGRESSAO estrutural — pega remocao de filtro mesmo sem dado no banco
# ==========================================================================
def test_toda_query_de_negocio_filtra_por_user_id():
    """Le o codigo-fonte da funcao e exige user_id em toda query sensivel.

    Vale por dois motivos: pega o defeito antes de existir dado que o revele,
    e cobre regras FUTURAS — quem acrescentar a regra 7 sem filtro quebra aqui,
    mesmo que os testes de comportamento acima nao a exercitem.
    """
    import io
    import re

    txt = io.open(BACKEND / "app/api/notifications.py", encoding="utf-8").read()
    corpo = txt.split("def _generate_proactive_notifications")[1]
    linhas = corpo.splitlines()

    sensiveis = ("Client", "Invoice", "Appointment", "Transaction",
                 "Opportunity", "Interaction")
    faltando = []
    for i, ln in enumerate(linhas):
        m = re.search(r"\.query\(\s*(" + "|".join(sensiveis) + r")\b", ln)
        if not m:
            continue
        bloco = []
        for j in range(i, min(i + 14, len(linhas))):
            bloco.append(linhas[j])
            if re.search(r"\.(all|first|count|scalar)\(\)", linhas[j]):
                break
        if "user_id" not in "\n".join(bloco):
            faltando.append((m.group(1), linhas[i].strip()[:60]))

    assert not faltando, (
        "Query(s) de dado de negocio SEM filtro de user_id em "
        f"_generate_proactive_notifications: {faltando}. "
        "Toda regra de notificacao filtra por user_id — nao existe notificacao "
        "'global' que leia tabela de cliente.")
