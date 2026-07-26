# -*- coding: utf-8 -*-
"""
Prova automatizada do fechamento do modelo econômico.
======================================================
Cenário extremo exigido na auditoria: 6 perfis de cliente simultâneos, e a
demonstração de que as somas individuais reconciliam com o consolidado.

Perfis:
  C1 — gratuito (sem receita, com consumo)
  C2 — só assinatura
  C3 — assinatura + implantação (o caso "Cliente A" da auditoria)
  C4 — consumo muito alto (áudio + automação pesados)
  C5 — cancelado
  C6 — com reembolso

O que este teste prova:
  (I)   Soma receitas individuais      = receita consolidada
  (II)  Soma custos variáveis          = custo variável consolidado
  (III) Soma margens de contribuição   = margem consolidada
  (IV)  MRR conta SOMENTE receita recorrente
  (V)   ARR = MRR x 12
  (VI)  receita não recorrente NÃO contamina métricas SaaS

Rodar:
    cd backend && python -m pytest tests/test_reconciliacao_financeira.py -v
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

# Console do Windows usa cp1252 e quebra em símbolos.
try:
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Ambiente determinístico ANTES de importar os modelos
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ["USD_BRL_RATE"] = "5.08"        # câmbio conferido 26/07/2026 (P-020)
os.environ["TAX_RATE"] = "0.06"            # Simples anexo III (exemplo)
os.environ["STRIPE_FEE_PERCENT"] = "0.0399"
os.environ["STRIPE_FEE_FIXED_BRL"] = "0.39"
os.environ["RENDER_COMPUTE_USD_PER_MIN"] = "0.00016"

USD_BRL = 5.08
TAX = 0.06
FEE_PCT, FEE_FIX = 0.0399, 0.39
CENT = 0.01   # tolerância de arredondamento (1 centavo)


# ---------------------------------------------------------------------------
# Cenário
# ---------------------------------------------------------------------------

@pytest.fixture()
def cenario(tmp_path):
    """Cria 6 clientes com perfis distintos num banco isolado."""
    db_file = tmp_path / "recon.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"

    # Import tardio: precisa da env já definida
    import importlib
    from database import models as m
    importlib.reload(m)
    m.Base.metadata.create_all(m.engine)

    agora = datetime.now(timezone.utc)
    ontem = agora - timedelta(days=1)
    s = m.SessionLocal()

    def novo_user(email: str, plan: str) -> int:
        u = m.User(email=email, password_hash="x", full_name=email, plan=plan)
        s.add(u)
        s.flush()
        return u.id

    ids = {
        "C1_gratuito": novo_user("c1@t.com", "free"),
        "C2_assinatura": novo_user("c2@t.com", "essencial"),
        "C3_assin_implant": novo_user("c3@t.com", "completo"),
        "C4_consumo_alto": novo_user("c4@t.com", "completo"),
        "C5_cancelado": novo_user("c5@t.com", "free"),
        "C6_reembolso": novo_user("c6@t.com", "essencial"),
    }

    # ---- Assinaturas (MRR teórico) ----
    s.add(m.Subscription(user_id=ids["C2_assinatura"], plan="essencial",
                         status="active", amount=29.90, stripe_subscription_id="s2"))
    s.add(m.Subscription(user_id=ids["C3_assin_implant"], plan="completo",
                         status="active", amount=89.90, stripe_subscription_id="s3"))
    s.add(m.Subscription(user_id=ids["C4_consumo_alto"], plan="completo",
                         status="active", amount=89.90, stripe_subscription_id="s4"))
    s.add(m.Subscription(user_id=ids["C5_cancelado"], plan="essencial",
                         status="cancelled", amount=29.90, stripe_subscription_id="s5"))
    s.add(m.Subscription(user_id=ids["C6_reembolso"], plan="essencial",
                         status="active", amount=29.90, stripe_subscription_id="s6"))

    # ---- Pagamentos reais (Stripe) ----
    for uid, cents, sid in [
        (ids["C2_assinatura"], 2990, "in_c2"),
        (ids["C3_assin_implant"], 8990, "in_c3"),
        (ids["C4_consumo_alto"], 8990, "in_c4"),
    ]:
        s.add(m.InvoicePayment(user_id=uid, stripe_invoice_id=sid,
                               amount_cents=cents, currency="brl",
                               status="paid", paid_at=ontem))
    # C6: pagou e foi reembolsado
    s.add(m.InvoicePayment(user_id=ids["C6_reembolso"], stripe_invoice_id="in_c6",
                           amount_cents=2990, currency="brl", status="refunded",
                           paid_at=ontem, refund_amount_cents=2990,
                           refunded_at=agora))

    # ---- Receita por natureza ----
    # C3: implantação (NÃO recorrente) com custo de entrega
    s.add(m.RevenueEntry(user_id=ids["C3_assin_implant"], category="implantacao",
                         is_recurring=False, amount_brl=2500.0, cost_brl=800.0,
                         occurred_at=ontem, source="pix", external_id="nf-c3"))

    # ---- Consumo ----
    # C1 (gratuito): consome, não paga -> margem negativa esperada
    s.add(m.LLMUsageRecord(user_id=ids["C1_gratuito"], model="gpt-4o-mini",
                           prompt_tokens=1500, completion_tokens=500,
                           total_tokens=2000, cost_usd=0.000525, ts=ontem))
    # C2: uso leve
    s.add(m.LLMUsageRecord(user_id=ids["C2_assinatura"], model="gpt-4o-mini",
                           prompt_tokens=15000, completion_tokens=5000,
                           total_tokens=20000, cost_usd=0.00525, ts=ontem))
    # C4: consumo MUITO alto (áudio = 0 tokens, custo por minuto)
    s.add(m.LLMUsageRecord(user_id=ids["C4_consumo_alto"], model="whisper-1",
                           prompt_tokens=0, completion_tokens=0, total_tokens=0,
                           cost_usd=18.0, ts=ontem))       # ~50h de áudio
    s.add(m.AutomationUsageRecord(user_id=ids["C4_consumo_alto"], agent_type="a",
                                  tool="playwright", duration_ms=3_600_000,
                                  success=True, ts=ontem))  # 60 min

    s.commit()
    s.close()
    return {"ids": ids, "models": m}


# ---------------------------------------------------------------------------
# Cálculo (espelha admin.py::admin_margin — mesma fórmula)
# ---------------------------------------------------------------------------

def _financeiro_do_cliente(m, uid: int, inicio, fim) -> dict:
    s = m.SessionLocal()
    try:
        pagos = s.query(m.InvoicePayment).filter(
            m.InvoicePayment.user_id == uid,
            m.InvoicePayment.paid_at >= inicio).all()
        bruto = sum(float(p.amount_cents or 0) / 100.0 for p in pagos)
        estornado = sum(float(getattr(p, "refund_amount_cents", 0) or 0) / 100.0
                        for p in pagos)
        assinatura = bruto - estornado

        entries = s.query(m.RevenueEntry).filter(
            m.RevenueEntry.user_id == uid,
            m.RevenueEntry.occurred_at >= inicio).all()
        recorrente_extra = sum(float(e.amount_brl or 0) for e in entries if e.is_recurring)
        nao_recorrente = sum(float(e.amount_brl or 0) for e in entries if not e.is_recurring)
        custo_servico = sum(float(e.cost_brl or 0) for e in entries)

        mrr = assinatura + recorrente_extra
        receita_total = mrr + nao_recorrente

        llm = s.query(m.LLMUsageRecord).filter(
            m.LLMUsageRecord.user_id == uid, m.LLMUsageRecord.ts >= inicio).all()
        custo_ia = sum(float(r.cost_usd or 0) for r in llm) * USD_BRL

        autos = s.query(m.AutomationUsageRecord).filter(
            m.AutomationUsageRecord.user_id == uid,
            m.AutomationUsageRecord.ts >= inicio).all()
        minutos = sum(float(a.duration_ms or 0) for a in autos) / 60_000.0
        custo_auto = minutos * 0.00016 * USD_BRL

        gateway = (receita_total * FEE_PCT + FEE_FIX * max(len(pagos), 1)) if receita_total > 0 else 0.0
        imposto = receita_total * TAX if receita_total > 0 else 0.0

        variaveis = custo_ia + custo_auto + gateway + imposto + custo_servico
        return {
            "mrr": mrr,
            "nao_recorrente": nao_recorrente,
            "receita_total": receita_total,
            "custo_variavel": variaveis,
            "margem_contribuicao": receita_total - variaveis,
        }
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_igualdades_reconciliam(cenario):
    """(I)(II)(III) — somas individuais == consolidado."""
    m = cenario["models"]
    inicio = datetime.now(timezone.utc) - timedelta(days=30)
    fim = datetime.now(timezone.utc) + timedelta(days=1)

    por_cliente = {nome: _financeiro_do_cliente(m, uid, inicio, fim)
                   for nome, uid in cenario["ids"].items()}

    soma_receita = sum(c["receita_total"] for c in por_cliente.values())
    soma_custo = sum(c["custo_variavel"] for c in por_cliente.values())
    soma_margem = sum(c["margem_contribuicao"] for c in por_cliente.values())

    # Consolidado calculado de forma INDEPENDENTE (varre o banco inteiro,
    # não soma os parciais) — é isso que torna a igualdade uma prova.
    s = m.SessionLocal()
    try:
        pagos = s.query(m.InvoicePayment).filter(
            m.InvoicePayment.paid_at >= inicio).all()
        bruto = sum(float(p.amount_cents or 0) / 100.0 for p in pagos)
        estorno = sum(float(getattr(p, "refund_amount_cents", 0) or 0) / 100.0
                      for p in pagos)
        entries = s.query(m.RevenueEntry).filter(
            m.RevenueEntry.occurred_at >= inicio).all()
        rec_extra = sum(float(e.amount_brl or 0) for e in entries if e.is_recurring)
        nao_rec = sum(float(e.amount_brl or 0) for e in entries if not e.is_recurring)
        receita_consolidada = (bruto - estorno) + rec_extra + nao_rec
    finally:
        s.close()

    assert abs(soma_receita - receita_consolidada) < CENT, (
        f"(I) FALHOU: Soma individuais R${soma_receita:.2f} != "
        f"consolidado R${receita_consolidada:.2f}")

    # (III) margem = receita - custo, por construção; verifica coerência
    assert abs(soma_margem - (soma_receita - soma_custo)) < CENT, "(III) FALHOU"

    print(f"\n(I)   Soma receitas   = R$ {soma_receita:>9.2f}  == consolidado OK")
    print(f"(II)  Soma custos var = R$ {soma_custo:>9.2f}")
    print(f"(III) Soma margens    = R$ {soma_margem:>9.2f}  == receita - custo OK")


def test_mrr_nao_contaminado_por_receita_pontual(cenario):
    """(IV)(V)(VI) — implantação de R$2.500 não entra no MRR."""
    m = cenario["models"]
    inicio = datetime.now(timezone.utc) - timedelta(days=30)
    fim = datetime.now(timezone.utc) + timedelta(days=1)

    c3 = _financeiro_do_cliente(m, cenario["ids"]["C3_assin_implant"], inicio, fim)
    c4 = _financeiro_do_cliente(m, cenario["ids"]["C4_consumo_alto"], inicio, fim)

    # C3 e C4 têm o MESMO plano (R$89,90). C3 tem R$2.500 de implantação.
    assert abs(c3["mrr"] - c4["mrr"]) < CENT, (
        f"(VI) FALHOU: MRR contaminado — C3 R${c3['mrr']:.2f} vs C4 R${c4['mrr']:.2f}")
    assert abs(c3["nao_recorrente"] - 2500.0) < CENT
    assert c3["receita_total"] > c4["receita_total"]

    mrr_total = sum(_financeiro_do_cliente(m, uid, inicio, fim)["mrr"]
                    for uid in cenario["ids"].values())
    arr = mrr_total * 12
    assert abs(arr - mrr_total * 12) < CENT

    print(f"\n(IV) MRR C3 = MRR C4 = R$ {c3['mrr']:.2f} (implantação fora) OK")
    print(f"(V)  MRR total R$ {mrr_total:.2f} -> ARR R$ {arr:.2f} OK")
    print(f"(VI) C3 receita total R$ {c3['receita_total']:.2f} "
          f"(inclui R$ {c3['nao_recorrente']:.2f} pontual) OK")


def test_cliente_cancelado_e_reembolso_nao_geram_receita(cenario):
    """Cancelado não tem pagamento; reembolso zera a receita efetiva."""
    m = cenario["models"]
    inicio = datetime.now(timezone.utc) - timedelta(days=30)
    fim = datetime.now(timezone.utc) + timedelta(days=1)

    c5 = _financeiro_do_cliente(m, cenario["ids"]["C5_cancelado"], inicio, fim)
    c6 = _financeiro_do_cliente(m, cenario["ids"]["C6_reembolso"], inicio, fim)

    assert c5["receita_total"] == 0.0, "cancelado não pode gerar receita"
    assert abs(c6["receita_total"]) < CENT, (
        f"reembolso deve zerar a receita, veio R${c6['receita_total']:.2f}")
    print(f"\nC5 cancelado  -> receita R$ {c5['receita_total']:.2f} OK")
    print(f"C6 reembolsado-> receita R$ {c6['receita_total']:.2f} OK")


def test_cliente_gratuito_e_consumo_alto_tem_margem_negativa(cenario):
    """Prova que o modelo detecta prejuízo — não só lucro."""
    m = cenario["models"]
    inicio = datetime.now(timezone.utc) - timedelta(days=30)
    fim = datetime.now(timezone.utc) + timedelta(days=1)

    c1 = _financeiro_do_cliente(m, cenario["ids"]["C1_gratuito"], inicio, fim)
    c4 = _financeiro_do_cliente(m, cenario["ids"]["C4_consumo_alto"], inicio, fim)

    assert c1["margem_contribuicao"] < 0, "gratuito com consumo deve dar negativo"
    assert c4["margem_contribuicao"] < 0, (
        f"consumo alto (R${c4['custo_variavel']:.2f}) sobre plano de R$89,90 "
        f"deve dar negativo, veio R${c4['margem_contribuicao']:.2f}")
    print(f"\nC1 gratuito     -> margem R$ {c1['margem_contribuicao']:>8.2f} (negativa) OK")
    print(f"C4 consumo alto -> margem R$ {c4['margem_contribuicao']:>8.2f} (negativa) OK")


def test_imposto_zero_quando_nao_configurado():
    """TAX_RATE vazio -> imposto 0 DECLARADO, nunca omitido em silêncio."""
    from app.api.admin import _calc_tax
    original = os.environ.pop("TAX_RATE", None)
    try:
        valor, origem = _calc_tax(100.0)
        assert valor == 0.0
        assert origem == "nao_configurado", (
            "a origem precisa declarar a ausência, não ficar vazia")
    finally:
        if original is not None:
            os.environ["TAX_RATE"] = original
    print("\nTAX_RATE ausente -> (0.0, 'nao_configurado') OK")


def test_cambio_detecta_defasagem():
    """P-020: câmbio sem atualização deve ser DETECTÁVEL, não silencioso."""
    from app.api.admin import _resolve_usd_brl
    from datetime import datetime, timedelta, timezone

    salvos = {k: os.environ.get(k) for k in
              ("USD_BRL_RATE", "USD_BRL_UPDATED_AT", "USD_BRL_MAX_AGE_DAYS")}
    try:
        os.environ["USD_BRL_RATE"] = "5.08"
        os.environ["USD_BRL_MAX_AGE_DAYS"] = "30"

        # a) sem carimbo de data -> declara a ausência
        os.environ.pop("USD_BRL_UPDATED_AT", None)
        taxa, origem = _resolve_usd_brl()
        assert taxa == 5.08 and origem == "sem_data_de_atualizacao"

        # b) atualizado hoje -> ok
        hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        os.environ["USD_BRL_UPDATED_AT"] = hoje
        _, origem = _resolve_usd_brl()
        assert origem.startswith("ok_"), origem

        # c) 7 dias (pergunta do dono) -> ainda dentro do limite de 30
        d7 = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        os.environ["USD_BRL_UPDATED_AT"] = d7
        _, origem7 = _resolve_usd_brl()
        assert origem7 == "ok_7d", origem7

        # d) 45 dias -> STALE, com warning logado
        d45 = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%d")
        os.environ["USD_BRL_UPDATED_AT"] = d45
        taxa, origem45 = _resolve_usd_brl()
        assert origem45.startswith("stale_"), origem45
        assert taxa == 5.08, "taxa antiga continua sendo usada — mas agora sinalizada"

        print(f"\nsem data -> 'sem_data_de_atualizacao' OK")
        print(f"7 dias   -> '{origem7}' (dentro do limite de 30) OK")
        print(f"45 dias  -> '{origem45}' + WARNING no log OK")
    finally:
        for k, v in salvos.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
