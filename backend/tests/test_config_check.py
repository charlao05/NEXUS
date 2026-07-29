# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
Checklist de ambiente — dois niveis
====================================

Principio (do dono, 26/07/2026):

    "O perigo maior nao e apenas falhar, e falhar em silencio.
     O objetivo e tornar impossivel um deploy incompleto parecer saudavel."

O que estes testes garantem:
  1. Env CRITICA ausente em PRODUCAO derruba o boot (nao sobe torto).
  2. Fora de producao NADA derruba — dev nao fica refem de config de producao.
  3. Env DEGRADADA nao derruba, mas aparece no /health como "degraded".
  4. Env SILENCIOSA (numero errado sem erro) e reportada.
  5. Placeholder ("re_COLE_AQUI") conta como AUSENTE.
  6. Nenhum VALOR de secret vaza no /health.

    cd backend && pytest tests/test_config_check.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config_check import (  # noqa: E402
    CRITICA, DEGRADADA, SILENCIOSA, ENVS,
    resumo_para_health, validar_no_startup, verificar,
)

TODAS = [s.nome for s in ENVS]


@pytest.fixture
def ambiente_limpo(monkeypatch):
    """Remove todas as envs do checklist para partir de um estado conhecido."""
    for nome in TODAS:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    return monkeypatch


def _criticas() -> list[str]:
    return [s.nome for s in ENVS if s.nivel == CRITICA]


# ==========================================================================
# 1-2. Fail-fast em producao, tolerancia em dev
# ==========================================================================
def test_producao_sem_env_critica_derruba_o_boot(ambiente_limpo):
    ambiente_limpo.setenv("ENVIRONMENT", "production")

    with pytest.raises(RuntimeError) as exc:
        validar_no_startup()

    msg = str(exc.value)
    for nome in _criticas():
        assert nome in msg, f"{nome} deveria aparecer na mensagem de erro"
    assert "Render" in msg, "a mensagem precisa dizer ONDE configurar"


def test_desenvolvimento_nao_derruba(ambiente_limpo):
    """Dev sobe mesmo sem nada — mas com os avisos registrados."""
    estado = validar_no_startup()  # nao levanta
    assert estado["is_production"] is False
    assert set(_criticas()).issubset(set(estado["criticas_faltando"]))


def test_producao_com_criticas_presentes_sobe(ambiente_limpo):
    ambiente_limpo.setenv("ENVIRONMENT", "production")
    ambiente_limpo.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
    ambiente_limpo.setenv("JWT_SECRET", "s" * 40)

    estado = validar_no_startup()  # nao levanta
    assert estado["criticas_faltando"] == []


# ==========================================================================
# 3-4. Degradada e silenciosa NAO derrubam, mas ficam visiveis
# ==========================================================================
def test_degradada_nao_derruba_mas_marca_health(ambiente_limpo):
    ambiente_limpo.setenv("ENVIRONMENT", "production")
    ambiente_limpo.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
    ambiente_limpo.setenv("JWT_SECRET", "s" * 40)

    validar_no_startup()
    saude = resumo_para_health()

    assert saude["status"] == "degraded", (
        "faltando RESEND/STRIPE_WEBHOOK/TAX_RATE, o /health nao pode dizer 'ok'")
    assert "RESEND_API_KEY" in saude["degradadas_faltando"]
    assert "STRIPE_WEBHOOK_SECRET" in saude["degradadas_faltando"]


def test_silenciosa_e_reportada(ambiente_limpo):
    """A categoria mais traicoeira: 200 com numero errado."""
    saude = resumo_para_health()
    assert "USD_BRL_RATE" in saude["silenciosas_faltando"]
    assert "STRIPE_FEE_PERCENT" in saude["silenciosas_faltando"]


def test_tudo_configurado_da_status_ok(ambiente_limpo):
    ambiente_limpo.setenv("ENVIRONMENT", "production")
    for spec in ENVS:
        ambiente_limpo.setenv(spec.nome, "valor-real-de-teste")

    saude = resumo_para_health()
    assert saude["status"] == "ok", saude
    assert saude["criticas_faltando"] == []
    assert saude["degradadas_faltando"] == []
    assert saude["silenciosas_faltando"] == []


# ==========================================================================
# 5. Placeholder e tao ruim quanto ausencia
# ==========================================================================
@pytest.mark.parametrize("valor", ["re_COLE_AQUI", "re_cole_aqui", "  re_COLE_AQUI  "])
def test_placeholder_conta_como_ausente(ambiente_limpo, valor):
    """.env.render carregou 're_COLE_AQUI' sem ninguem notar."""
    ambiente_limpo.setenv("RESEND_API_KEY", valor)
    assert "RESEND_API_KEY" in verificar()["degradadas_faltando"], (
        f"placeholder {valor!r} passou como configurado")


def test_valor_real_nao_e_confundido_com_placeholder(ambiente_limpo):
    ambiente_limpo.setenv("RESEND_API_KEY", "re_9fK2mPq7XyZ")
    assert "RESEND_API_KEY" not in verificar()["degradadas_faltando"]


# ==========================================================================
# 5b. Automacao web — a falha de build nao pode ficar muda
# ==========================================================================
def test_browser_ausente_e_detectado(monkeypatch, tmp_path):
    """REGRESSAO: `playwright install chromium || true` engole o erro no build.

    Sem esta deteccao, o app sobe verde, o router carrega (o PACOTE playwright
    importa normalmente) e a automacao so quebra no PRIMEIRO USO do usuario,
    com "Executable doesn't exist at /ms-playwright/...".
    """
    from app.core import config_check as cc

    # Aponta o Playwright para um diretorio vazio: simula o build que falhou.
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    monkeypatch.setattr(cc.os.path, "isdir", lambda p: str(p) == str(tmp_path))

    ok, motivo = cc.browser_disponivel(forcar=True)
    assert ok is False, "diretorio sem chromium deveria acusar indisponibilidade"
    assert "chromium" in motivo.lower()


def test_browser_presente_e_reconhecido(monkeypatch, tmp_path):
    from app.core import config_check as cc

    (tmp_path / "chromium-1148").mkdir()
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

    ok, motivo = cc.browser_disponivel(forcar=True)
    assert ok is True, motivo


def test_health_reporta_automacao_web(ambiente_limpo):
    """O estado da automacao precisa estar VISIVEL no /health."""
    from app.core import config_check as cc

    cc.browser_disponivel(forcar=True)  # limpa cache de outros testes
    saude = resumo_para_health()
    assert "automacao_web" in saude, "o /health precisa reportar a automacao web"
    assert "disponivel" in saude["automacao_web"]
    assert "motivo" in saude["automacao_web"]


# ==========================================================================
# 5c. Stripe — presenca da chave NAO basta
# ==========================================================================
#
# INCIDENTE REAL (28/07/2026 23:05 UTC): STRIPE_SECRET_KEY estava DEFINIDA no
# Render e o Stripe a rejeitava. O checkout devolvia 503, a pagina de planos
# mostrava "Sistema de pagamento em manutencao" e o /health dizia que estava
# tudo bem. Quem descobriu foi um clique em "Assinar" — ou seja, seria um
# cliente descobrindo.
#
# Estes testes protegem a diferenca entre "a env existe" e "a chave funciona".

def test_chave_ausente_e_detectada(monkeypatch):
    from app.core import config_check as cc

    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    ok, motivo = cc.stripe_autentica(forcar=True)
    assert ok is False
    assert "ausente" in motivo.lower()


def test_chave_presente_mas_rejeitada_e_detectada(monkeypatch):
    """O CASO DO INCIDENTE: env definida, Stripe recusa."""
    from app.core import config_check as cc

    class _AuthenticationError(Exception):
        pass

    class _FakeAccount:
        @staticmethod
        def retrieve():
            raise _AuthenticationError("Invalid API Key provided")

    class _FakeStripe:
        api_key = None
        Account = _FakeAccount

    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_parece_valida_mas_nao_e")
    monkeypatch.setitem(sys.modules, "stripe", _FakeStripe)

    ok, motivo = cc.stripe_autentica(forcar=True)
    assert ok is False, "chave rejeitada pelo Stripe tem de acusar"
    assert "rejeitada" in motivo.lower()
    assert "assinar" in motivo.lower(), "o motivo precisa dizer o IMPACTO"


def test_chave_valida_nao_acusa(monkeypatch):
    from app.core import config_check as cc

    class _FakeAccount:
        @staticmethod
        def retrieve():
            return {"id": "acct_fake"}

    class _FakeStripe:
        api_key = None
        Account = _FakeAccount

    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_chave_boa")
    monkeypatch.setitem(sys.modules, "stripe", _FakeStripe)

    ok, motivo = cc.stripe_autentica(forcar=True)
    assert ok is True, motivo
    assert "live" in motivo


def test_falha_de_rede_nao_vira_alarme_falso(monkeypatch):
    """Blip de rede NAO pode ser reportado como chave invalida.

    Alarme falso destroi a confianca no alerta — e alerta em que ninguem
    confia e igual a nao ter alerta. Foi assim que o CI ficou 134 runs
    vermelho sem ninguem olhar.
    """
    from app.core import config_check as cc

    class _APIConnectionError(Exception):
        pass

    class _FakeAccount:
        @staticmethod
        def retrieve():
            raise _APIConnectionError("connection dropped")

    class _FakeStripe:
        api_key = None
        Account = _FakeAccount

    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_chave_boa")
    monkeypatch.setitem(sys.modules, "stripe", _FakeStripe)

    ok, motivo = cc.stripe_autentica(forcar=True)
    assert ok is True, "falha de rede nao pode ser tratada como chave invalida"
    assert "indeterminado" in motivo.lower()


def test_health_reporta_stripe(ambiente_limpo):
    from app.core import config_check as cc

    cc.stripe_autentica(forcar=True)
    saude = resumo_para_health()
    assert "stripe" in saude, "o /health precisa reportar o estado do Stripe"
    assert "autentica" in saude["stripe"]
    assert "motivo" in saude["stripe"]


def test_envs_de_cobranca_estao_no_checklist():
    """REGRESSAO da lacuna: faltavam a chave que COBRA e os 3 price IDs.

    O checklist tinha STRIPE_WEBHOOK_SECRET (receber eventos) e nao tinha
    STRIPE_SECRET_KEY (cobrar). Sem cobranca nao ha negocio.
    """
    nomes = {s.nome for s in ENVS}
    obrigatorias = {
        "STRIPE_SECRET_KEY",
        "STRIPE_PRICE_ESSENCIAL",
        "STRIPE_PRICE_PROFISSIONAL",
        "STRIPE_PRICE_COMPLETO",
    }
    faltando = obrigatorias - nomes
    assert not faltando, f"envs de cobranca fora do checklist: {sorted(faltando)}"


# ==========================================================================
# 6. O /health nao pode vazar secret
# ==========================================================================
def test_health_nao_expoe_valores(ambiente_limpo):
    segredo = "whsec_valor_super_secreto_123"
    ambiente_limpo.setenv("STRIPE_WEBHOOK_SECRET", segredo)
    ambiente_limpo.setenv("JWT_SECRET", "jwt_secreto_abc")

    texto = repr(resumo_para_health())
    assert segredo not in texto, "VAZAMENTO: valor de secret no /health"
    assert "jwt_secreto_abc" not in texto, "VAZAMENTO: JWT_SECRET no /health"


def test_toda_env_do_checklist_tem_nivel_e_justificativa():
    """Cada linha precisa dizer o que quebra e onde — senao vira lista morta."""
    for spec in ENVS:
        assert spec.nivel in (CRITICA, DEGRADADA, SILENCIOSA), spec.nome
        assert spec.o_que_quebra.strip(), f"{spec.nome} sem 'o que quebra'"
        assert spec.onde.strip(), f"{spec.nome} sem referencia de codigo"


def test_criticas_sao_poucas_e_deliberadas():
    """Guarda contra inflacao da lista critica.

    Classificar algo como critico por engano derruba o servico num redeploy —
    no Render, app fora do ar ate corrigir pelo painel. A lista deve crescer por
    decisao explicita, nunca por descuido.
    """
    criticas = _criticas()
    assert len(criticas) <= 3, (
        f"lista critica cresceu para {criticas}. Cada item aqui pode derrubar "
        "producao — confirme que a ausencia corrompe dados ou quebra toda "
        "requisicao, de forma invisivel.")
