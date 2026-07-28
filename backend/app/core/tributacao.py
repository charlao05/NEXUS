# -*- coding: utf-8 -*-
"""
Regime tributário DA EMPRESA que opera o NEXUS — não do cliente dela.
=====================================================================

⚠️ ESCOPO. Este módulo calcula o imposto do NEXUS como negócio, para o painel
de margem (/api/admin/margin). Ele NÃO é usado para nenhum cálculo fiscal
entregue a usuário — isso é responsabilidade do `contabilidade_agent`, que
permanece intocado.

POR QUE EXISTE (26-27/07/2026)
------------------------------
`admin.py::_calc_tax` aplicava `receita × TAX_RATE`, ou seja, um percentual
sobre a receita. Isso modela o **Simples Nacional**. Mas o dono é **MEI**, e
MEI paga **DAS FIXO** — R$ 86,05/mês em serviços, independentemente de faturar
R$ 500 ou R$ 6.000 no mês.

A diferença não é de precisão, é de NATUREZA:

    percentual  -> custo VARIÁVEL  -> entra na margem de contribuição
    valor fixo  -> custo FIXO      -> fica FORA da margem de contribuição

Tratar DAS fixo como percentual distorce o unit economics por cliente. Com o
regime MEI, a margem de contribuição por cliente **não muda** com o imposto —
e isso é o comportamento correto, coerente com a opção C já adotada (custo fixo
fora do unit economics).

O QUE ESTE MÓDULO NÃO FAZ
-------------------------
Não escolhe regime, não recomenda enquadramento e não dá conselho tributário.
Ele implementa o MECANISMO e declara a fonte de cada número; a escolha do
regime é decisão contábil do dono.

FONTES DOS NÚMEROS
------------------
- MEI: constantes de `agents/contabilidade_agent.py:43-77` (importadas, não
  duplicadas) — salário mínimo 2026, INSS 5%, DAS por atividade, limite anual.
- Simples Nacional: faixas informadas por env. Os defaults abaixo refletem a
  1ª faixa de cada anexo e estão marcados como PREMISSA — precisam de
  confirmação do contador antes de sustentar qualquer decisão.

Configuração:
    TAX_REGIME = mei | simples_anexo_iii | simples_anexo_v | nenhum
    MEI_ATIVIDADE = servicos | comercio | industria | comercio_servicos
    TAX_RATE = usado apenas nos regimes Simples (ex.: "0.06")
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

REGIME_MEI = "mei"
REGIME_SIMPLES_III = "simples_anexo_iii"
REGIME_SIMPLES_V = "simples_anexo_v"
REGIME_NENHUM = "nenhum"

REGIMES_VALIDOS = (REGIME_MEI, REGIME_SIMPLES_III, REGIME_SIMPLES_V, REGIME_NENHUM)

# Natureza do imposto por regime — o que decide se entra ou não na margem
# de contribuição. Esta tabela é a razão de ser do módulo.
NATUREZA = {
    REGIME_MEI: "fixo",
    REGIME_SIMPLES_III: "variavel",
    REGIME_SIMPLES_V: "variavel",
    REGIME_NENHUM: "nao_configurado",
}

# PREMISSA — 1ª faixa de cada anexo (até R$ 180.000/ano de RBT12).
# NÃO CONFIRMADO com contador. Ajustável por env.
_ALIQUOTA_PADRAO = {
    REGIME_SIMPLES_III: 0.06,   # Anexo III — Fator R >= 28%
    REGIME_SIMPLES_V: 0.155,    # Anexo V  — Fator R <  28%
}

# Fator R: divisor entre os anexos III e V para serviços.
FATOR_R_LIMITE = 0.28


def regime_atual() -> str:
    raw = (os.getenv("TAX_REGIME", "") or "").strip().lower()
    if not raw:
        return REGIME_NENHUM
    if raw not in REGIMES_VALIDOS:
        logger.warning(
            "TAX_REGIME invalido (%r). Validos: %s. Tratando como nao configurado.",
            raw, ", ".join(REGIMES_VALIDOS),
        )
        return REGIME_NENHUM
    return raw


def das_mei_mensal() -> tuple[float, str]:
    """Valor FIXO do DAS-MEI no mês. Retorna (valor, origem).

    Importa as constantes do contabilidade_agent em vez de duplicá-las: elas
    já são usadas para responder ao usuário e foram conferidas contra a regra
    fiscal. Ter dois lugares com o mesmo número é como o valor errado entra.
    """
    try:
        from agents.contabilidade_agent import DAS_VALORES_2026  # type: ignore
    except Exception as e:  # noqa: BLE001
        logger.error("Nao foi possivel importar DAS_VALORES_2026: %s", e)
        return 0.0, "constantes_indisponiveis"

    atividade = (os.getenv("MEI_ATIVIDADE", "servicos") or "servicos").strip().lower()
    if atividade not in DAS_VALORES_2026:
        logger.warning(
            "MEI_ATIVIDADE invalida (%r) — usando 'servicos'. Validas: %s",
            atividade, ", ".join(DAS_VALORES_2026),
        )
        atividade = "servicos"

    return float(DAS_VALORES_2026[atividade]), f"das_mei_2026_{atividade}"


def aliquota_simples() -> tuple[float, str]:
    """Alíquota do regime Simples configurado. Retorna (aliquota, origem)."""
    regime = regime_atual()
    if regime not in _ALIQUOTA_PADRAO:
        return 0.0, "regime_nao_e_simples"

    raw = (os.getenv("TAX_RATE", "") or "").strip()
    if raw:
        try:
            valor = float(raw)
            if 0.0 <= valor <= 1.0:
                return valor, "TAX_RATE_configurado"
            logger.warning("TAX_RATE fora de 0..1 (%r) — usando o padrao do anexo", raw)
        except ValueError:
            logger.warning("TAX_RATE invalido (%r) — usando o padrao do anexo", raw)

    return _ALIQUOTA_PADRAO[regime], f"padrao_1a_faixa_{regime}_PREMISSA"


def calcular_imposto(receita_periodo_brl: float) -> dict:
    """Imposto do período e, principalmente, a NATUREZA dele.

    `entra_na_margem_de_contribuicao` é o campo que decide onde o número entra:
      True  -> custo variável, dentro da margem de contribuição
      False -> custo fixo, fora dela (caso do MEI)
    """
    regime = regime_atual()
    natureza = NATUREZA[regime]

    if regime == REGIME_MEI:
        valor, origem = das_mei_mensal()
        return {
            "regime": regime,
            "natureza": "fixo",
            "valor_brl": round(valor, 2),
            "aliquota_efetiva": None,
            "origem": origem,
            "entra_na_margem_de_contribuicao": False,
            "observacao": (
                "DAS-MEI e valor FIXO mensal: nao varia com a receita, logo e "
                "custo fixo e fica fora da margem de contribuicao."
            ),
        }

    if regime in (REGIME_SIMPLES_III, REGIME_SIMPLES_V):
        aliq, origem = aliquota_simples()
        return {
            "regime": regime,
            "natureza": "variavel",
            "valor_brl": round(max(0.0, receita_periodo_brl) * aliq, 2),
            "aliquota_efetiva": aliq,
            "origem": origem,
            "entra_na_margem_de_contribuicao": True,
            "observacao": (
                "Aliquota da 1a faixa. NAO considera a formula de aliquota "
                "efetiva por RBT12 nem confirmacao contabil — ver docstring."
            ),
        }

    return {
        "regime": REGIME_NENHUM,
        "natureza": "nao_configurado",
        "valor_brl": 0.0,
        "aliquota_efetiva": None,
        "origem": "TAX_REGIME nao configurado",
        "entra_na_margem_de_contribuicao": False,
        "observacao": (
            "Sem TAX_REGIME, a margem reportada e PRE-IMPOSTO. Configure "
            "TAX_REGIME=mei (ou o anexo do Simples) no ambiente."
        ),
    }


def status_limite_mei(receita_12m_brl: float) -> dict:
    """Onde a receita está em relação ao teto do MEI.

    Existe porque o teto chega cedo: com assinatura de R$ 89,90, o limite anual
    equivale a poucas dezenas de assinantes — e ultrapassar muda o regime, logo
    muda a natureza do imposto e o unit economics junto.
    """
    try:
        from agents.contabilidade_agent import (  # type: ignore
            LIMITE_ANUAL_MEI, LIMITE_EXCESSO_20_PERCENT,
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "indeterminavel", "motivo": f"constantes indisponiveis: {e}"}

    receita = max(0.0, receita_12m_brl)
    pct = (receita / LIMITE_ANUAL_MEI * 100) if LIMITE_ANUAL_MEI else 0.0

    if receita > LIMITE_EXCESSO_20_PERCENT:
        status = "desenquadrado"
    elif receita > LIMITE_ANUAL_MEI:
        status = "excedeu_com_tolerancia"
    elif pct >= 80:
        status = "atencao"
    else:
        status = "dentro"

    return {
        "status": status,
        "receita_12m_brl": round(receita, 2),
        "limite_anual_brl": LIMITE_ANUAL_MEI,
        "percentual_usado": round(pct, 1),
        "margem_ate_o_limite_brl": round(max(0.0, LIMITE_ANUAL_MEI - receita), 2),
    }
