# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
E-002 — Teste de INTEGRACAO do endpoint /api/admin/margin
==========================================================

POR QUE ESTE ARQUIVO EXISTE (critica do dono, 26/07/2026):

    "O teste ainda prova a implementacao, nao o sistema."

O test_reconciliacao_financeira.py (E-001) ESPELHA a formula do admin.py: ele
recalcula em Python o mesmo que a rota calcula. Se a formula estiver errada nos
dois lugares, o teste passa e o erro sobrevive. E um teste de aritmetica.

Este arquivo faz o oposto:
  1. popula o banco,
  2. chama a ROTA REAL via HTTP (TestClient),
  3. compara com CONSTANTES LITERAIS calculadas a mao.

REGRA INEGOCIAVEL DESTE ARQUIVO
-------------------------------
Nenhum valor esperado pode ser derivado chamando _calc_tax, _calc_gateway_fee,
_resolve_usd_brl ou qualquer helper do admin.py. Os numeros abaixo foram feitos
a mao e estao documentados termo a termo. Se alguem mudar a formula na rota,
ESTE TESTE TEM QUE QUEBRAR — e isso e o objetivo, nao um efeito colateral.

Prova de que funciona: mude STRIPE_FEE_PERCENT de 0.0399 para 0.05 no cenario e
o teste falha. O E-001 nao falharia.

O QUE ELE JA ENCONTROU
----------------------
Bug real de payload: a chave "mrr_brl" aparecia DUAS VEZES no mesmo dict
"revenue" (admin.py linhas 1133 e 1143). Em Python a segunda sobrescreve a
primeira, entao o MRR teorico do plano nunca chegou ao payload. Um teste que
espelha a formula nao tem como ver isso — a formula estava certa; o dict, nao.

    cd backend && pytest tests/test_margin_endpoint_integracao.py -v
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from starlette.testclient import TestClient

# ==========================================================================
# CENARIO — todos os valores de entrada, fixados
# ==========================================================================
USD_BRL = 5.20
FEE_PCT = 0.0399
FEE_FIX = 0.39
TAX = 0.06

ASSINATURA_BRL = 89.90        # Subscription.amount (status active)
IMPLANTACAO_BRL = 2500.00     # RevenueEntry nao-recorrente
IMPLANTACAO_CUSTO_BRL = 400.00  # custo de entrega do servico
LLM_COST_USD = 0.0015         # 10.000 tokens de input gpt-4o-mini

# --------------------------------------------------------------------------
# ARITMETICA FEITA A MAO — nao chamar helper nenhum para chegar nestes numeros
# --------------------------------------------------------------------------
# receita
#   MRR do plano ............ 89.90                (Subscription.amount)
#   efetiva (mrr_theoretical) 89.90                (sem invoice paga no periodo)
#   nao-recorrente .......... 2500.00              (RevenueEntry)
#   TOTAL ................... 89.90 + 2500.00    = 2589.90
ESPERADO_MRR = 89.90
ESPERADO_NAO_RECORRENTE = 2500.00
ESPERADO_RECEITA_TOTAL = 2589.90

# custos variaveis
#   IA .......... 0.0015 USD * 5.20             = 0.0078 BRL
#   gateway ..... 89.90 * 0.0399 + 0.39
#                 = 3.587010 + 0.39             = 3.977010 -> 3.98 (round 2)
#   imposto ..... 2589.90 * 0.06                = 155.394  -> 155.39 (round 2)
#   servico ..... custo de entrega              = 400.00
#   automacao ... nenhum AutomationUsageRecord  = 0.00
ESPERADO_LLM_BRL = 0.0078
ESPERADO_GATEWAY_BRL = 3.98
ESPERADO_TAX_BRL = 155.39
ESPERADO_SERVICO_BRL = 400.00

#   soma (sem arredondar as parcelas):
#     0.0078 + 3.977010 + 155.394 + 400.00      = 559.378810
ESPERADO_VARIAVEIS = 559.3788

# margem de contribuicao = receita total - variaveis
#     2589.90 - 559.378810                      = 2030.521190 -> 2030.52
ESPERADO_CONTRIBUICAO = 2030.52

TOL = 0.011  # tolerancia de centavo (o payload arredonda em 2 casas)


# ==========================================================================
# FIXTURES — mesmo padrao de tests/test_fase3.py:17-72
# ==========================================================================
@pytest.fixture(scope="module")
def app():
    backend = Path(__file__).parent.parent
    sys.path.insert(0, str(backend))
    os.environ.setdefault("JWT_SECRET", "test-secret-margin-integracao")
    os.environ.setdefault(
        "NEXUS_DB_PATH", str(backend / "data" / "test_margin_integracao.db"))
    os.environ["ADMIN_EMAILS"] = "margin-admin@nexus.com"

    from main import app as _app
    from database.models import init_db
    init_db()
    return _app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


@pytest.fixture(scope="module")
def admin_headers(client):
    email, password = "margin-admin@nexus.com", "Admin1234!"
    client.post("/api/auth/signup", json={
        "email": email, "password": password, "full_name": "Admin Margem"})
    resp = client.post("/api/auth/login", json={
        "email": email, "password": password})
    data = resp.json()
    assert "access_token" in data, f"login admin falhou: {data}"
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture(scope="module")
def cenario(client):
    """Cria o cliente do cenario e devolve o user_id.

    CENARIO SINTETICO — usado apenas para exercitar a rota. Os R$ 2.500 de
    implantacao NAO sao exemplo de negocio: nenhum cliente real pagou
    implantacao, e nenhum preco de servico foi validado com mercado.
    """
    from database.models import (
        SessionLocal, User, Subscription, LLMUsageRecord, RevenueEntry)

    email = "cliente-margem@nexus.com"
    client.post("/api/auth/signup", json={
        "email": email, "password": "Cliente1234!", "full_name": "Cliente Margem"})

    agora = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None, "usuario do cenario nao foi criado"
        uid = user.id

        # limpa execucoes anteriores (o .db do teste persiste entre runs)
        db.query(Subscription).filter(Subscription.user_id == uid).delete()
        db.query(LLMUsageRecord).filter(LLMUsageRecord.user_id == uid).delete()
        db.query(RevenueEntry).filter(RevenueEntry.user_id == uid).delete()

        db.add(Subscription(
            user_id=uid, plan="completo", status="active",
            amount=ASSINATURA_BRL, currency="brl"))
        db.add(LLMUsageRecord(
            ts=agora, user_id=uid, model="gpt-4o-mini",
            prompt_tokens=10_000, completion_tokens=0, total_tokens=10_000,
            duration_ms=800, cost_usd=LLM_COST_USD, agent_type="contabilidade"))
        db.add(RevenueEntry(
            user_id=uid, category="implantacao", is_recurring=False,
            amount_brl=IMPLANTACAO_BRL, cost_brl=IMPLANTACAO_CUSTO_BRL,
            occurred_at=agora, source="teste_integracao",
            external_id="e002-implantacao",
            notes="CENARIO SINTETICO - validacao de logica, nao exemplo de negocio"))
        db.commit()
        return uid
    finally:
        db.close()


@pytest.fixture
def envs(monkeypatch):
    """Fixa as envs economicas. Cada teste ajusta o que precisar."""
    monkeypatch.setenv("USD_BRL_RATE", str(USD_BRL))
    monkeypatch.setenv("STRIPE_FEE_PERCENT", str(FEE_PCT))
    monkeypatch.setenv("STRIPE_FEE_FIXED_BRL", str(FEE_FIX))
    monkeypatch.setenv("TAX_RATE", str(TAX))
    monkeypatch.setenv("ENVIRONMENT", "test")
    return monkeypatch


def _margin(client, headers, uid):
    resp = client.get(f"/api/admin/margin?user_id={uid}", headers=headers)
    assert resp.status_code == 200, f"/margin falhou: {resp.status_code} {resp.text}"
    return resp.json()


# ==========================================================================
# TESTES
# ==========================================================================
def test_receita_separa_mrr_de_pontual(client, admin_headers, cenario, envs):
    """A rota nao pode misturar implantacao com MRR.

    E o erro que motivou a tabela revenue_entries: um cliente com implantacao
    aparecia no /margin como se valesse so a assinatura.
    """
    p = _margin(client, admin_headers, cenario)["revenue"]

    assert p["mrr_brl"] == pytest.approx(ESPERADO_MRR, abs=TOL), \
        f"MRR contaminado por receita pontual: {p['mrr_brl']}"
    assert p["nonrecurring_brl"] == pytest.approx(ESPERADO_NAO_RECORRENTE, abs=TOL)
    assert p["total_brl"] == pytest.approx(ESPERADO_RECEITA_TOTAL, abs=TOL)
    print(f"\n  MRR R$ {p['mrr_brl']:.2f} | pontual R$ {p['nonrecurring_brl']:.2f}"
          f" | total R$ {p['total_brl']:.2f}  OK")


def test_chave_mrr_duplicada_no_payload(client, admin_headers, cenario, envs):
    """REGRESSAO: "mrr_brl" existia 2x no mesmo dict e a 2a sobrescrevia a 1a.

    O MRR teorico do plano nunca chegava ao cliente da API. Nenhum teste que
    espelha a formula pode detectar isso — a formula estava correta; o dict nao.
    """
    p = _margin(client, admin_headers, cenario)["revenue"]

    assert "plan_mrr_brl" in p, (
        "campo do MRR teorico do plano ausente — a chave duplicada voltou")
    assert p["plan_mrr_brl"] == pytest.approx(ESPERADO_MRR, abs=TOL)
    print(f"\n  plan_mrr_brl R$ {p['plan_mrr_brl']:.2f} exposto (antes: engolido)  OK")


def test_custos_batem_com_aritmetica_manual(client, admin_headers, cenario, envs):
    """Cada parcela contra o numero feito a mao no cabecalho deste arquivo."""
    c = _margin(client, admin_headers, cenario)["costs"]

    assert c["llm_brl"] == pytest.approx(ESPERADO_LLM_BRL, abs=0.0001), \
        f"IA: esperado {ESPERADO_LLM_BRL}, veio {c['llm_brl']}"
    assert c["gateway_fee_brl"] == pytest.approx(ESPERADO_GATEWAY_BRL, abs=TOL), \
        f"gateway: esperado {ESPERADO_GATEWAY_BRL}, veio {c['gateway_fee_brl']}"
    assert c["tax_brl"] == pytest.approx(ESPERADO_TAX_BRL, abs=TOL), \
        f"imposto: esperado {ESPERADO_TAX_BRL}, veio {c['tax_brl']}"
    assert c["variable_total_brl"] == pytest.approx(ESPERADO_VARIAVEIS, abs=TOL)
    print(f"\n  IA {c['llm_brl']:.4f} | gateway {c['gateway_fee_brl']:.2f}"
          f" | imposto {c['tax_brl']:.2f} | variaveis {c['variable_total_brl']:.4f}  OK")


def test_margem_de_contribuicao(client, admin_headers, cenario, envs):
    """Contribuicao = receita total - variaveis, contra o valor manual."""
    d = _margin(client, admin_headers, cenario)
    m = d["margin"]

    assert m["contribution_brl"] == pytest.approx(ESPERADO_CONTRIBUICAO, abs=TOL), \
        f"contribuicao: esperado {ESPERADO_CONTRIBUICAO}, veio {m['contribution_brl']}"

    # auto-consistencia: o payload nao pode se contradizer
    recomposto = d["revenue"]["total_brl"] - d["costs"]["variable_total_brl"]
    assert m["contribution_brl"] == pytest.approx(recomposto, abs=TOL), \
        "payload inconsistente: margem nao bate com receita - custos do proprio payload"
    print(f"\n  contribuicao R$ {m['contribution_brl']:.2f}"
          f" (= {d['revenue']['total_brl']:.2f} - {d['costs']['variable_total_brl']:.4f})  OK")


def test_margin_basis_after_tax(client, admin_headers, cenario, envs):
    """Com TAX_RATE configurado, a base declarada e AFTER_TAX."""
    m = _margin(client, admin_headers, cenario)["margin"]

    assert m["margin_basis"] == "AFTER_TAX", f"base errada: {m['margin_basis']}"
    assert m["tax_configured"] is True
    assert m["tax_rate"] == pytest.approx(TAX)
    print(f"\n  margin_basis={m['margin_basis']} tax_rate={m['tax_rate']}  OK")


def test_margin_basis_pre_tax_sem_aliquota(client, admin_headers, cenario, envs):
    """Sem TAX_RATE em dev, responde — mas declarando que e PRE_TAX.

    O numero continua util para desenvolvimento; o que nao pode e ser lido como
    margem liquida.
    """
    envs.delenv("TAX_RATE", raising=False)
    d = _margin(client, admin_headers, cenario)

    assert d["margin"]["margin_basis"] == "PRE_TAX"
    assert d["margin"]["tax_configured"] is False
    assert d["margin"]["tax_rate"] is None
    assert d["costs"]["tax_source"] == "nao_configurado"
    assert d["costs"]["tax_brl"] == 0.0
    print("\n  sem TAX_RATE -> margin_basis=PRE_TAX, tax_rate=None  OK")


def test_bloqueia_em_producao_sem_aliquota(client, admin_headers, cenario, envs):
    """Em producao sem TAX_RATE a rota RECUSA calcular (decisao do dono).

    Melhor 503 do que um numero pre-imposto que alguem interpreta como liquido.
    """
    envs.delenv("TAX_RATE", raising=False)
    envs.setenv("ENVIRONMENT", "production")

    resp = client.get(f"/api/admin/margin?user_id={cenario}", headers=admin_headers)
    assert resp.status_code == 503, f"esperado 503, veio {resp.status_code}"
    detail = resp.json()["detail"]
    assert detail["error"] == "TAX_RATE_NOT_CONFIGURED", detail

    # /margin/all tem o mesmo guard
    resp_all = client.get("/api/admin/margin/all", headers=admin_headers)
    assert resp_all.status_code == 503, \
        f"/margin/all respondeu {resp_all.status_code} sem aliquota em producao"
    print("\n  producao sem TAX_RATE -> 503 em /margin e /margin/all  OK")


def test_producao_com_aliquota_responde(client, admin_headers, cenario, envs):
    """O guard bloqueia a ausencia de configuracao, nao a producao."""
    envs.setenv("ENVIRONMENT", "production")
    envs.setenv("TAX_RATE", str(TAX))

    d = _margin(client, admin_headers, cenario)
    assert d["margin"]["margin_basis"] == "AFTER_TAX"
    print("\n  producao COM TAX_RATE -> 200 e AFTER_TAX  OK")


def test_qualidade_do_cambio_no_payload(client, admin_headers, cenario, envs):
    """exchange_status declara a confianca do cambio; age_days=None e desconhecido."""
    envs.delenv("USD_BRL_UPDATED_AT", raising=False)
    c = _margin(client, admin_headers, cenario)["costs"]
    assert c["exchange_status"] == "manual_override", c["exchange_status"]
    assert c["exchange_age_days"] is None, "idade desconhecida deve ser None, nunca 0"

    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    envs.setenv("USD_BRL_UPDATED_AT", hoje)
    envs.setenv("USD_BRL_MAX_AGE_DAYS", "30")
    c = _margin(client, admin_headers, cenario)["costs"]
    assert c["exchange_status"] == "fresh", c["exchange_status"]
    assert c["exchange_age_days"] == 0

    envs.setenv("USD_BRL_UPDATED_AT", "2020-01-01")  # muito velho
    c = _margin(client, admin_headers, cenario)["costs"]
    assert c["exchange_status"] == "expired", c["exchange_status"]
    assert c["exchange_age_days"] > 1000
    print("\n  cambio: manual_override / fresh / expired  OK")
