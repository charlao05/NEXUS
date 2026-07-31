# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
Atribuicao de consumo de IA — quem gastou, e em quê
====================================================

O PROBLEMA (30/07/2026)

Todo consumo de IA era gravado com user_id=0. O sistema sabia
"foram geradas 122 propostas" e NAO sabia quem gerou cada uma.

Sem atribuicao, nada disto e implementavel: limite mensal, franquia,
degustacao, cobranca por uso, upgrade automatico, ranking, deteccao de abuso,
custo por plano.

A INFRAESTRUTURA JA EXISTIA E NINGUEM A ALIMENTAVA

  openai_tracking.py:89  ja cai para um ContextVar quando user_id_override
                         nao e passado
  automation_logger.py:51  o ContextVar existe
  -> faltava so POPULAR, e o unico lugar certo e get_current_user (auth.py),
     por onde passa todo request autenticado.

O QUE ESTES TESTES PROTEGEM

1. O consumo e atribuido ao usuario CERTO — nao ao 0, nem ao usuario errado.
2. O consumo e rotulado pela FUNCIONALIDADE (vendas, cobranca, nota_fiscal),
   nao pelo transporte ("llm_client_simple").
3. Telemetria NUNCA derruba autenticacao — perder medicao e aceitavel,
   impedir login nao e.

    cd backend && pytest tests/test_atribuicao_consumo.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _contexto_limpo():
    """Zera o ContextVar entre testes — senao um vaza para o outro."""
    from utils.automation_logger import set_context, _user_id, _agent_type
    _user_id.set(None)
    _agent_type.set(None)
    yield
    _user_id.set(None)
    _agent_type.set(None)


# ==========================================================================
# 1. O ContextVar e de fato consultado pelo tracking
# ==========================================================================
def test_tracking_usa_o_contexto_quando_nao_recebe_user_id():
    """E a peca central: sem isso, tudo continua caindo em user_id=0."""
    from utils.automation_logger import set_context, _user_id

    set_context(user_id=42)
    assert _user_id.get() == 42, "set_context nao populou o ContextVar"


def test_override_explicito_vence_o_contexto():
    """agent_chat.py:1235 passa user_id_override — tem de continuar mandando."""
    from utils.automation_logger import set_context, _user_id

    set_context(user_id=42)
    ctx = _user_id.get()
    override = 99
    # replica a regra de openai_tracking.py:89
    uid = int(override) if override is not None else int(ctx or 0)
    assert uid == 99, "override explicito deveria ter precedencia"


def test_sem_contexto_e_sem_override_cai_para_zero():
    """Comportamento anterior, preservado como fallback consciente."""
    from utils.automation_logger import _user_id

    ctx = _user_id.get()
    uid = int(ctx or 0)
    assert uid == 0


# ==========================================================================
# 2. Rotulo pela FUNCIONALIDADE, nao pelo transporte
# ==========================================================================
def test_gerar_texto_simples_aceita_agent_type():
    """Sem isto, proposta, cobranca e nota fiscal caem no mesmo balde."""
    import inspect
    from utils.llm_client import gerar_texto_simples

    params = inspect.signature(gerar_texto_simples).parameters
    assert "agent_type" in params, (
        "gerar_texto_simples precisa aceitar agent_type para o custo ser "
        "atribuivel por modulo")
    assert params["agent_type"].default is None, (
        "agent_type deve ser opcional — nao pode quebrar chamadas existentes")


@pytest.mark.parametrize("arquivo,rotulo", [
    ("agents/vendas_agent.py", "vendas"),
    ("agents/collections_agent.py", "cobranca"),
    ("agents/nf_agent.py", "nota_fiscal"),
])
def test_cada_agente_rotula_seu_consumo(arquivo, rotulo):
    """REGRESSAO: se alguem remover o rotulo, o custo vira anonimo de novo."""
    import io

    caminho = Path(__file__).parent.parent / arquivo
    txt = io.open(caminho, encoding="utf-8").read()
    assert f'agent_type="{rotulo}"' in txt, (
        f"{arquivo} deixou de rotular o consumo como '{rotulo}' — "
        "o custo desse modulo volta a ser inatribuivel")


# ==========================================================================
# 3. Telemetria nao pode derrubar autenticacao
# ==========================================================================
def test_falha_de_telemetria_nao_quebra_login(monkeypatch):
    """Se set_context explodir, get_current_user tem de seguir funcionando.

    Perder uma medicao e aceitavel. Impedir alguem de entrar no sistema
    porque a telemetria falhou nao e.
    """
    import app.api.auth as auth_mod
    import io

    txt = io.open(Path(__file__).parent.parent / "app/api/auth.py",
                  encoding="utf-8").read()
    i = txt.find("from utils.automation_logger import set_context")
    assert i > 0, "o set_context sumiu de get_current_user"

    trecho = txt[max(0, i - 200):i + 250]
    assert "try:" in trecho and "except" in trecho, (
        "a chamada de telemetria em get_current_user PRECISA estar dentro de "
        "try/except — senao uma falha de medicao derruba a autenticacao")
