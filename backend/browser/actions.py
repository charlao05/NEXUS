"""Ações primitivas utilizadas pelos agentes para manipular páginas."""

from __future__ import annotations

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

try:
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..utils.logging_utils import get_logger

logger = get_logger("browser.actions")


def abrir_url(page: Page, url: str) -> None:
    logger.info("Abrindo URL: %s", url)
    try:
        page.goto(url, wait_until="load")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Falha ao abrir URL {url}: {exc}") from exc


def clicar(page: Page, selector: str) -> None:
    logger.info("Clicando no seletor: %s", selector)
    try:
        page.click(selector)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Falha ao clicar no seletor {selector}: {exc}") from exc


def digitar(page: Page, selector: str, texto: str, secret: bool = False) -> None:
    visivel = "***" if secret else texto
    logger.info("Digitando no seletor %s -> %s", selector, visivel)
    try:
        page.fill(selector, texto)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Falha ao digitar no seletor {selector}: {exc}") from exc


def esperar_selector(page: Page, selector: str, timeout_ms: int = 10_000) -> None:
    logger.info("Esperando seletor %s (timeout %sms)", selector, timeout_ms)
    try:
        page.wait_for_selector(selector, timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        raise TimeoutError(
            f"Timeout ao esperar o seletor {selector} após {timeout_ms}ms"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Erro inesperado ao esperar o seletor {selector}: {exc}"
        ) from exc


def type_text(page: Page, selector: str, text: str) -> None:
    """Digita texto em um campo (alias para digitar com semantics melhorada)."""
    logger.info("Digitando em %s", selector)
    try:
        page.fill(selector, text)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Falha ao digitar em {selector}: {exc}") from exc


def press_key(page: Page, key: str) -> None:
    """Pressiona uma tecla específica (ex: 'Enter', 'Tab', 'Escape')."""
    logger.info("Pressionando tecla: %s", key)
    try:
        page.keyboard.press(key)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Falha ao pressionar tecla {key}: {exc}") from exc


def wait_seconds(page: Page, seconds: int) -> None:
    """Aguarda N segundos."""
    logger.info("Aguardando %d segundo(s)", seconds)
    try:
        page.wait_for_timeout(seconds * 1000)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Erro ao aguardar {seconds} segundos: {exc}") from exc
