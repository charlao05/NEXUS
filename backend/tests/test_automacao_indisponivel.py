# -*- coding: utf-8 -*-
"""Automacao web recusa com mensagem clara quando o browser nao existe."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))
from fastapi import HTTPException


def test_recusa_com_503_quando_browser_ausente(monkeypatch):
    """Em producao o chromium NAO esta instalado (medido em /health).

    Sem este guard, o Playwright estourava "Executable doesn't exist" e o erro
    cru chegava ao usuario.
    """
    from app.api import agent_automation as aa
    from app.core import config_check as cc

    monkeypatch.setattr(cc, "browser_disponivel", lambda *a, **k: (False, "chromium ausente"))

    with pytest.raises(HTTPException) as exc:
        aa._exigir_browser()

    assert exc.value.status_code == 503
    d = exc.value.detail
    assert d["error"] == "AUTOMACAO_WEB_INDISPONIVEL"
    assert "indisponível" in d["message"].lower()
    # A mensagem precisa tranquilizar sobre o RESTO do produto
    assert "demais" in d["message"].lower()


def test_nao_recusa_quando_browser_existe(monkeypatch):
    from app.api import agent_automation as aa
    from app.core import config_check as cc

    monkeypatch.setattr(cc, "browser_disponivel", lambda *a, **k: (True, "ok"))
    aa._exigir_browser()  # nao deve levantar
