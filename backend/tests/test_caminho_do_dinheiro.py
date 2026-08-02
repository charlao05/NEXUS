# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
O CAMINHO DO DINHEIRO — os passos que ficam entre "quero pagar" e "tenho acesso"
================================================================================

POR QUE ESTE ARQUIVO EXISTE

Em 01/08/2026 uma medicao do caminho do primeiro cliente real mostrou que, dos
12 passos, os UNICOS 4 sem teste eram exatamente os que tocam dinheiro:

    gerar proposta · pagar (checkout) · RECEBER PAGAMENTO · cancelar

O repositorio inteiro tinha ZERO teste de webhook. 489 testes verdes, e a
lacuna estava toda de um lado so.

O QUE ISSO CUSTOU — dois defeitos que a ausencia destes testes escondeu

1. Eu quebrei o pagamento no commit 60f10de (a pia) e 4 jobs de CI aprovaram.
   Webhook do Stripe nao tem Depends(get_current_user) — e autenticado por
   assinatura — entao nao havia tenant no contexto, e dispatch_stripe_event
   levantava TenantContextMissing na primeira query de Subscription.

   E o modo de falha era o pior possivel: _stripe_webhook_handler.py:602
   engole a excecao e devolve 200 ao Stripe. O Stripe marca como entregue e
   NUNCA reenvia. O cliente pagava e o plano nao ativava — permanentemente.

2. TODAS as rotas vivas de billing.py devolviam 500, e isso e ANTERIOR a pia.
   `get_current_user` devolve um DICT (auth.py:341), mas as rotas anotavam
   `current_user: User` e faziam `current_user.id` — AttributeError. Ver
   faturas, ver assinatura e cancelar assinatura NUNCA funcionaram.

A ASSERCAO QUE FALTAVA, E QUE E O CORACAO DESTE ARQUIVO

    200 NAO E SUCESSO NUM WEBHOOK.

O handler devolve 200 mesmo quando falha. Qualquer teste que so olhasse o
status teria passado com o pagamento quebrado. Aqui o corpo e inspecionado:
`{"status": "error"}` e FALHA de teste.

    cd backend && pytest tests/test_caminho_do_dinheiro.py -v
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("JWT_SECRET", "test-secret-dinheiro")
os.environ.setdefault("NEXUS_DB_PATH", str(BACKEND / "data" / "test_dinheiro.db"))
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_falsa_para_teste")
os.environ.setdefault("STRIPE_PRICE_ESSENCIAL", "price_teste_essencial")

CLIENTE = {"email": "pagante@teste.com", "password": "Pagante1234!"}


@pytest.fixture(scope="module")
def app():
    from main import app as _app
    from database.models import init_db
    init_db()
    return _app


@pytest.fixture(scope="module")
def cli(app):
    from starlette.testclient import TestClient
    return TestClient(app)


@pytest.fixture(scope="module")
def pagante(cli):
    """Usuario recem-criado, no plano free — como todo primeiro cliente."""
    from database.models import SessionLocal, User, Subscription
    from app.core.tenant import sem_tenant

    cli.post("/api/auth/signup", json={**CLIENTE, "full_name": "Cliente Pagante"})
    token = cli.post("/api/auth/login", json=CLIENTE).json()["access_token"]

    db = SessionLocal()
    with sem_tenant("preparar o cenario de pagamento do teste"):
        try:
            u = db.query(User).filter(User.email == CLIENTE["email"]).first()
            uid = u.id
            # o .db de teste persiste entre execucoes
            db.query(Subscription).filter(Subscription.user_id == uid).delete()
            u.plan = "free"
            db.commit()
        finally:
            db.close()

    return {"token": token, "id": uid,
            "headers": {"Authorization": f"Bearer {token}"}}


def _plano_no_banco(uid: int) -> str:
    from database.models import SessionLocal, User
    from app.core.tenant import sem_tenant
    db = SessionLocal()
    with sem_tenant("conferir o plano gravado"):
        try:
            return db.query(User).filter(User.id == uid).first().plan
        finally:
            db.close()


def _evento_pagamento(uid: int, plano: str = "essencial",
                      sessao: str = "cs_test_1") -> bytes:
    """checkout.session.completed REALISTA.

    ⚠️ Um payload esqueleto NAO serve: o handler retorna cedo, antes de tocar
    o banco, e devolve 200. Foi exatamente assim que meu primeiro smoke me
    disse que estava tudo bem com o pagamento quebrado.
    """
    return json.dumps({
        "id": f"evt_{sessao}", "type": "checkout.session.completed",
        "data": {"object": {
            "id": sessao, "mode": "subscription",
            "customer": "cus_teste", "subscription": f"sub_{sessao}",
            "amount_total": 2990, "currency": "brl",
            "client_reference_id": str(uid),
            "metadata": {"user_id": str(uid), "plan": plano},
            "customer_details": {"email": CLIENTE["email"]},
        }},
    }).encode()


# ==========================================================================
# PASSO 10 — RECEBER PAGAMENTO. O que eu quebrei, e o mais grave dos quatro.
# ==========================================================================
def test_pagamento_ativa_o_plano_do_cliente(cli, pagante):
    """A cadeia inteira: cliente paga -> evento chega -> plano muda.

    Se este teste existisse em 01/08/2026, o commit da pia nao teria passado.
    """
    uid = pagante["id"]
    assert _plano_no_banco(uid) == "free", "o cenario tem de comecar no free"

    r = cli.post("/api/auth/webhook/stripe",
                 content=_evento_pagamento(uid, sessao="cs_ativa_1"),
                 headers={"stripe-signature": "t=1,v1=x",
                          "content-type": "application/json"})

    assert r.status_code == 200
    corpo = r.json()

    # ⚠️ A ASSERCAO QUE FALTAVA. O handler devolve 200 ATE QUANDO FALHA
    # (_stripe_webhook_handler.py:602, com comentario explicito). Olhar so o
    # status status e o que deixaria o pagamento quebrado passar batido.
    assert corpo.get("status") != "error", (
        "O webhook devolveu 200 com status=error — o Stripe vai marcar como "
        f"entregue e NUNCA reenviar. O cliente pagou e nao recebeu acesso.\n"
        f"erro: {corpo.get('error')}")
    assert corpo.get("action") == "subscription_created", corpo

    assert _plano_no_banco(uid) == "essencial", (
        "O plano do usuario NAO mudou depois do pagamento. E o pior modo de "
        "falha possivel com cliente real: ele pagou e continua sem acesso.")


def test_assinatura_foi_criada_no_banco(cli, pagante):
    from database.models import SessionLocal, Subscription
    from app.core.tenant import sem_tenant

    db = SessionLocal()
    with sem_tenant("conferir a assinatura criada pelo webhook"):
        try:
            sub = (db.query(Subscription)
                   .filter(Subscription.user_id == pagante["id"])
                   .first())
        finally:
            db.close()
    assert sub is not None, "nenhuma Subscription criada apos o pagamento"
    assert sub.status == "active"


def test_pagamento_repetido_nao_duplica(cli, pagante):
    """Idempotencia: o Stripe reenvia o mesmo evento quando ha timeout."""
    uid = pagante["id"]
    payload = _evento_pagamento(uid, sessao="cs_repetido_1")
    h = {"stripe-signature": "t=1,v1=x", "content-type": "application/json"}

    cli.post("/api/auth/webhook/stripe", content=payload, headers=h)
    r2 = cli.post("/api/auth/webhook/stripe", content=payload, headers=h)

    assert r2.status_code == 200
    assert r2.json().get("status") != "error"

    from database.models import SessionLocal, Subscription
    from app.core.tenant import sem_tenant
    db = SessionLocal()
    with sem_tenant("contar assinaturas do teste"):
        try:
            n = (db.query(Subscription)
                 .filter(Subscription.stripe_checkout_session_id == "cs_repetido_1")
                 .count())
        finally:
            db.close()
    assert n <= 1, f"o mesmo checkout gerou {n} assinaturas — idempotencia quebrou"


def test_webhook_recusa_assinatura_invalida(cli):
    """Sem isso, um POST forjado ativa plano de graca."""
    import app.api._stripe_webhook_handler as h

    if not os.getenv("STRIPE_WEBHOOK_SECRET"):
        pytest.skip("STRIPE_WEBHOOK_SECRET ausente — sem secret nao ha o que validar "
                    "(o proprio handler avisa isso no log)")
    r = cli.post("/api/auth/webhook/stripe", content=b'{"type":"x"}',
                 headers={"stripe-signature": "assinatura-falsa"})
    assert r.status_code == 400


# ==========================================================================
# PASSO 9 — PAGAR (checkout)
# ==========================================================================
def test_checkout_devolve_url_de_pagamento(cli, pagante, monkeypatch):
    """Se o checkout nao devolve URL, o cliente nem chega a pagar."""
    import stripe

    class _Sessao:
        id = "cs_test_checkout"
        url = "https://checkout.stripe.com/c/pay/cs_test_checkout"

    monkeypatch.setattr(stripe.checkout.Session, "create",
                        classmethod(lambda cls, **kw: _Sessao()))

    r = cli.post("/api/auth/checkout", headers=pagante["headers"],
                 json={"plan": "essencial"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert "checkout.stripe.com" in json.dumps(corpo), corpo


def test_checkout_recusa_plano_inexistente(cli, pagante):
    r = cli.post("/api/auth/checkout", headers=pagante["headers"],
                 json={"plan": "plano_que_nao_existe"})
    assert r.status_code >= 400


# ==========================================================================
# PASSO 12 — CANCELAR, e as rotas de billing que devolviam 500
# ==========================================================================
def test_ver_minhas_faturas_responde(cli, pagante):
    """REGRESSAO de E-043: esta rota devolvia 500 em toda chamada.

    `get_current_user` devolve dict; a rota anotava `current_user: User` e
    fazia `current_user.id`. Nunca funcionou, e nunca teve teste.
    """
    r = cli.get("/api/auth/invoices", headers=pagante["headers"])
    assert r.status_code == 200, f"{r.status_code} — {r.text[:200]}"
    assert isinstance(r.json(), list)


def test_ver_minha_assinatura_responde(cli, pagante):
    """REGRESSAO de E-043 — mesmo defeito."""
    r = cli.get("/api/auth/subscription", headers=pagante["headers"])
    assert r.status_code == 200, f"{r.status_code} — {r.text[:200]}"


def test_cancelar_assinatura_nao_explode(cli, pagante, monkeypatch):
    """REGRESSAO de E-043. O passo 12 do caminho do primeiro cliente.

    Nao exige sucesso do Stripe (a chave e falsa no teste) — exige que a rota
    ENCONTRE a assinatura e trate o erro. 500 aqui e AttributeError, nao
    problema de pagamento.
    """
    import stripe
    monkeypatch.setattr(stripe.Subscription, "modify",
                        classmethod(lambda cls, *a, **kw: {"status": "active"}))

    r = cli.delete("/api/auth/subscription", headers=pagante["headers"])
    assert r.status_code != 500, (
        f"a rota de cancelamento explodiu: {r.text[:200]}")
    assert r.status_code in (200, 404), r.status_code


# ==========================================================================
# PASSO 6 — GERAR PROPOSTA (o que justifica o plano Profissional)
# ==========================================================================
def test_gerar_proposta_devolve_texto(cli, pagante, monkeypatch):
    """A unica acao de vendas que consome IA — e a que sustenta o preco.

    O LLM e mockado de proposito: o teste prova o CAMINHO (rota -> agente ->
    preco -> texto), nao a qualidade da redacao do modelo.
    """
    import utils.llm_client as llm
    monkeypatch.setattr(llm, "gerar_texto_simples",
                        lambda *a, **kw: "Proposta gerada pelo modelo.")

    from database.models import SessionLocal, User
    from app.core.tenant import sem_tenant
    db = SessionLocal()
    with sem_tenant("liberar o agente de vendas para o teste"):
        try:
            u = db.query(User).filter(User.id == pagante["id"]).first()
            u.plan = "completo"      # vendas exige profissional+
            db.commit()
        finally:
            db.close()

    r = cli.post("/api/agents/vendas/execute", headers=pagante["headers"],
                 json={"action": "gerar_proposta",
                       "parameters": {"service_type": "landing_page",
                                      "cliente": "Padaria do Bairro",
                                      "escopo": "site institucional"}})
    assert r.status_code == 200, r.text
    corpo = r.json()
    texto = json.dumps(corpo, ensure_ascii=False)
    assert len(texto) > 80, f"proposta vazia demais: {texto[:200]}"
    assert corpo.get("status") in ("success", "ok"), corpo


def test_calcular_orcamento_nao_usa_ia(cli, pagante):
    """Nivel 1 do agente de vendas: deterministico, custo R$ 0,00.

    E o que pode ir para qualquer plano sem custo marginal — a base da
    estrategia de degustacao.
    """
    r = cli.post("/api/agents/vendas/execute", headers=pagante["headers"],
                 json={"action": "calcular_orcamento",
                       "parameters": {"service_type": "landing_page",
                                      "urgency": "high"}})
    assert r.status_code == 200, r.text
    assert "R$" in json.dumps(r.json(), ensure_ascii=False)
