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


def iniciar_navegador(
    browser_name: Optional[str] = None,
    headless: Optional[bool] = None,
) -> Tuple[Any, Any, Any]:
    """
    Inicia o Playwright e um navegador (chromium/firefox/webkit)
    e devolve (playwright, browser, page).

    - Usa DEFAULT_BROWSER do .env se browser_name não for passado.
    - Usa BROWSER_HEADLESS do .env se headless não for passado.
      Em produção (ENVIRONMENT=production), default é True.
      Em dev, default é False para ver a janela.
    """
    browser_name = browser_name or os.getenv("DEFAULT_BROWSER", "chromium")

    if headless is None:
        env_headless = os.getenv("BROWSER_HEADLESS", "")
        if env_headless.lower() in ("1", "true", "yes"):
            headless = True
        elif env_headless.lower() in ("0", "false", "no"):
            headless = False
        else:
            # Produção = headless; dev = com janela
            headless = os.getenv("ENVIRONMENT", "development") == "production"

    logger.info(f"Iniciando navegador Playwright: {browser_name} (headless={headless})")

    p = sync_playwright().start()

    launch_opts = {"headless": headless}

    if browser_name.lower() == "firefox":
        browser = p.firefox.launch(**launch_opts)
    elif browser_name.lower() == "webkit":
        browser = p.webkit.launch(**launch_opts)
    else:
        browser = p.chromium.launch(**launch_opts)

    page = browser.new_page()
    return p, browser, page


def fechar_navegador(
    p: Optional[Any],
    browser: Optional[Any],
    delay_seconds: int = 0,
) -> None:
    """
    Fecha o browser e o Playwright com segurança.
    Chamado no finally do agente, mesmo se der erro no meio.

    Args:
        delay_seconds: Tempo de espera antes de fechar (para inspeção manual em dev).
                       Default 0 (sem delay). Use BROWSER_CLOSE_DELAY env para configurar.
    """
    delay = delay_seconds or int(os.getenv("BROWSER_CLOSE_DELAY", "0"))
    if delay > 0:
        logger.info(f"Aguardando {delay}s antes de fechar o navegador para inspeção.")
        time.sleep(delay)

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
