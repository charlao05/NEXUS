# src/browser/playwright_client.py

"""
Camada de integração com o Playwright (modo síncrono).

Responsável por:
- iniciar o Playwright e o navegador
- devolver uma page pronta para uso
- fechar tudo com segurança no final
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional, Tuple

from playwright.sync_api import sync_playwright

try:
    from backend.utils.logging_utils import get_logger
except ImportError:
    from utils.logging_utils import get_logger

logger = get_logger(__name__)


def iniciar_navegador(browser_name: Optional[str] = None) -> Tuple[Any, Any, Any]:
    """
    Inicia o Playwright e um navegador (chromium/firefox/webkit)
    e devolve (playwright, browser, page).

    - Usa DEFAULT_BROWSER do .env se browser_name não for passado.
    - headless=False para você VER a janela abrindo.
    """
    browser_name = browser_name or os.getenv("DEFAULT_BROWSER", "chromium")
    logger.info(f"Iniciando navegador Playwright: {browser_name}")

    p = sync_playwright().start()

    if browser_name.lower() == "firefox":
        browser = p.firefox.launch(headless=False)
    elif browser_name.lower() == "webkit":
        browser = p.webkit.launch(headless=False)
    else:
        browser = p.chromium.launch(headless=False)

    page = browser.new_page()
    return p, browser, page


def fechar_navegador(p: Optional[Any], browser: Optional[Any]) -> None:
    """
    Fecha o browser e o Playwright com segurança.
    Chamado no finally do agente, mesmo se der erro no meio.
    """

    # ⏱ Tempo que a janela fica aberta DEPOIS de terminar o plano
    logger.info("Aguardando 15 segundos antes de fechar o navegador para inspeção.")
    time.sleep(15)  # se quiser mais tempo, aumenta esse número

    logger.info("Fechando navegador Playwright.")
    try:
        if browser is not None:
            browser.close()
    except Exception as exc:
        logger.warning(f"Erro ao fechar browser: {exc}")

    try:
        if p is not None:
            p.stop()
    except Exception as exc:
        logger.warning(f"Erro ao encerrar Playwright: {exc}")
