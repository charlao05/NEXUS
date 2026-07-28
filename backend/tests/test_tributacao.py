# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
Regime tributario da empresa que opera o NEXUS
===============================================

O QUE ESTES TESTES PROTEGEM (27/07/2026)

`_calc_tax` aplicava SEMPRE `receita x TAX_RATE`, o que modela o Simples
Nacional. O dono e MEI, e MEI paga DAS FIXO: R$ 86,05/mes em servicos, igual
faturando R$ 500 ou R$ 6.000.

A diferenca nao e de precisao, e de NATUREZA do custo:

    percentual -> variavel -> DENTRO da margem de contribuicao
    fixo       -> fixo     -> FORA dela

O teste central e test_das_mei_nao_varia_com_a_receita: se ele falhar, o
imposto voltou a ser tratado como percentual e o unit economics por cliente
esta distorcido.

ESCOPO: isto e o imposto do NEXUS COMO NEGOCIO, para o painel de margem. Nada
aqui e usado em calculo fiscal entregue a usuario — isso e do
contabilidade_agent, que nao foi tocado.

    cd backend && pytest tests/test_tributacao.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.tributacao import (  # noqa: E402
    REGIME_MEI, REGIME_NENHUM, REGIME_SIMPLES_III, REGIME_SIMPLES_V,
    calcular_imposto, das_mei_mensal, regime_atual, status_limite_mei,
)


@pytest.fixture
def limpo(monkeypatch):
    for k in ("TAX_REGIME", "TAX_RATE", "MEI_ATIVIDADE"):
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


# ==========================================================================
# 1. MEI — o caso que motivou o modulo
# ==========================================================================
def test_das_mei_nao_varia_com_a_receita(limpo):
    """TESTE CENTRAL: DAS-MEI e FIXO. Se falhar, virou percentual de novo."""
    limpo.setenv("TAX_REGIME", "mei")

    baixa = calcular_imposto(500.0)
    alta = calcular_imposto(6000.0)

    assert baixa["valor_brl"] == alta["valor_brl"], (
        "DAS-MEI variou com a receita — foi tratado como percentual. "
        f"R$500 -> {baixa['valor_brl']}, R$6000 -> {alta['valor_brl']}")
    assert baixa["natureza"] == "fixo"


def test_mei_fica_fora_da_margem_de_contribuicao(limpo):
    """Custo fixo nao entra na margem de contribuicao (opcao C ja adotada)."""
    limpo.setenv("TAX_REGIME", "mei")
    r = calcular_imposto(5000.0)
    assert r["entra_na_margem_de_contribuicao"] is False, (
        "DAS fixo entrando na margem de contribuicao distorce o unit economics")


def test_valor_do_das_vem_do_contabilidade_agent(limpo):
    """Nao duplicar constante fiscal: o numero vem de uma fonte so."""
    from agents.contabilidade_agent import DAS_VALORES_2026

    limpo.setenv("TAX_REGIME", "mei")
    limpo.setenv("MEI_ATIVIDADE", "servicos")

    valor, origem = das_mei_mensal()
    assert valor == DAS_VALORES_2026["servicos"], (
        "o DAS do painel divergiu do que o agente responde ao usuario")
    assert valor == pytest.approx(86.05, abs=0.01)
    assert "servicos" in origem


@pytest.mark.parametrize("atividade,esperado", [
    ("servicos", 86.05),
    ("comercio", 82.05),
    ("comercio_servicos", 87.05),
])
def test_das_por_atividade(limpo, atividade, esperado):
    limpo.setenv("TAX_REGIME", "mei")
    limpo.setenv("MEI_ATIVIDADE", atividade)
    assert das_mei_mensal()[0] == pytest.approx(esperado, abs=0.01)


def test_atividade_invalida_cai_para_servicos(limpo):
    limpo.setenv("TAX_REGIME", "mei")
    limpo.setenv("MEI_ATIVIDADE", "atividade_que_nao_existe")
    assert das_mei_mensal()[0] == pytest.approx(86.05, abs=0.01)


# ==========================================================================
# 2. Simples — o oposto: variavel e dentro da margem
# ==========================================================================
def test_simples_e_proporcional_e_entra_na_margem(limpo):
    limpo.setenv("TAX_REGIME", "simples_anexo_v")

    r1 = calcular_imposto(1000.0)
    r2 = calcular_imposto(2000.0)

    assert r2["valor_brl"] == pytest.approx(r1["valor_brl"] * 2, abs=0.01), (
        "imposto do Simples deveria dobrar ao dobrar a receita")
    assert r1["natureza"] == "variavel"
    assert r1["entra_na_margem_de_contribuicao"] is True


def test_anexo_iii_e_menor_que_anexo_v(limpo):
    """Fator R: III (6%) vs V (15,5%) — a diferenca e material."""
    limpo.setenv("TAX_REGIME", "simples_anexo_iii")
    iii = calcular_imposto(10_000.0)["valor_brl"]
    limpo.setenv("TAX_REGIME", "simples_anexo_v")
    v = calcular_imposto(10_000.0)["valor_brl"]
    assert iii < v, "Anexo III precisa ser menor que o V"


def test_tax_rate_sobrescreve_o_padrao_do_anexo(limpo):
    limpo.setenv("TAX_REGIME", "simples_anexo_iii")
    limpo.setenv("TAX_RATE", "0.09")
    r = calcular_imposto(1000.0)
    assert r["valor_brl"] == pytest.approx(90.0, abs=0.01)
    assert r["aliquota_efetiva"] == pytest.approx(0.09)


# ==========================================================================
# 3. Nao configurado e valores invalidos
# ==========================================================================
def test_sem_regime_declara_que_nao_esta_configurado(limpo):
    r = calcular_imposto(5000.0)
    assert r["regime"] == REGIME_NENHUM
    assert r["valor_brl"] == 0.0
    assert "PRE-IMPOSTO" in r["observacao"].upper()


def test_regime_invalido_nao_quebra(limpo):
    limpo.setenv("TAX_REGIME", "lucro_presumido_que_nao_implementamos")
    assert regime_atual() == REGIME_NENHUM


@pytest.mark.parametrize("valor", ["-0.5", "1.5", "abc"])
def test_tax_rate_invalido_cai_para_o_padrao(limpo, valor):
    limpo.setenv("TAX_REGIME", "simples_anexo_iii")
    limpo.setenv("TAX_RATE", valor)
    r = calcular_imposto(1000.0)
    assert r["valor_brl"] == pytest.approx(60.0, abs=0.01), (
        "TAX_RATE invalido deveria cair para o padrao do anexo (6%)")


# ==========================================================================
# 4. Limite do MEI — o regime muda quando o negocio cresce
# ==========================================================================
@pytest.mark.parametrize("receita,status", [
    (30_000.0, "dentro"),
    (70_000.0, "atencao"),               # >= 80% do teto
    (85_000.0, "excedeu_com_tolerancia"),  # entre 81k e 97,2k
    (120_000.0, "desenquadrado"),          # acima de 97,2k
])
def test_status_do_limite_mei(receita, status):
    assert status_limite_mei(receita)["status"] == status


def test_limite_usa_a_constante_oficial():
    from agents.contabilidade_agent import LIMITE_ANUAL_MEI
    assert status_limite_mei(0.0)["limite_anual_brl"] == LIMITE_ANUAL_MEI


# ==========================================================================
# 5. Integracao com o /margin
# ==========================================================================
def test_calc_tax_do_admin_respeita_o_regime(limpo):
    """O painel de margem tem de usar o mesmo mecanismo."""
    from app.api.admin import _calc_tax

    limpo.setenv("TAX_REGIME", "mei")
    valor, origem = _calc_tax(89.90)
    assert valor == pytest.approx(86.05, abs=0.01)
    assert "FIXO" in origem, f"origem deveria marcar FIXO, veio {origem}"


def test_tax_rate_sozinho_continua_funcionando(limpo):
    """Compatibilidade: quem configurou so TAX_RATE nao pode quebrar."""
    from app.api.admin import _calc_tax

    limpo.setenv("TAX_RATE", "0.06")
    valor, origem = _calc_tax(1000.0)
    assert valor == pytest.approx(60.0, abs=0.01)
    assert "aliquota" in origem
