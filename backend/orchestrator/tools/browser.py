"""
Browser tools para o orquestrador LangGraph.
=============================================
Registra ferramentas de automação de navegador que delegam
para a infraestrutura Playwright existente em backend/browser/.

Cada tool segue o protocolo do act_node:
    fn(params: dict, state: AgentState) -> dict

As tools são síncronas (Playwright sync API) e gerenciam o
ciclo de vida do browser automaticamente.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.orchestrator.nodes.act import register_tool
from backend.orchestrator.state import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estado compartilhado do browser (lazy init)
# ---------------------------------------------------------------------------
_browser_state: dict[str, Any] = {
    "playwright": None,
    "browser": None,
    "page": None,
}


def _ensure_browser() -> Any:
    """Garante que o browser está inicializado. Retorna a page."""
    if _browser_state["page"] is None:
        from backend.browser.playwright_client import iniciar_navegador
        pw, browser, page = iniciar_navegador()
        _browser_state["playwright"] = pw
        _browser_state["browser"] = browser
        _browser_state["page"] = page
        logger.info("🌐 Browser inicializado para automação")
    return _browser_state["page"]


def shutdown_browser() -> None:
    """Encerra o browser de forma segura. Chamado ao final da tarefa."""
    if _browser_state["browser"] is not None:
        try:
            from backend.browser.playwright_client import fechar_navegador
            fechar_navegador(
                _browser_state["playwright"],
                _browser_state["browser"],
            )
        except Exception as e:
            logger.warning(f"Erro ao fechar browser: {e}")
        finally:
            _browser_state["playwright"] = None
            _browser_state["browser"] = None
            _browser_state["page"] = None
            logger.info("🌐 Browser encerrado")


# ---------------------------------------------------------------------------
# Tools registradas no act_node
# ---------------------------------------------------------------------------

@register_tool("browser_navigate")
def browser_navigate(params: dict, state: AgentState) -> dict[str, Any]:
    """Navega para uma URL."""
    from backend.browser.actions import abrir_url
    url = params.get("url", "")
    if not url:
        return {"success": False, "error": "URL não informada"}
    
    page = _ensure_browser()
    abrir_url(page, url)
    title = page.title()
    return {
        "success": True,
        "url": url,
        "title": title,
        "message": f"Navegou para {url} — título: {title}",
    }


@register_tool("browser_click")
def browser_click(params: dict, state: AgentState) -> dict[str, Any]:
    """Clica em um elemento da página."""
    from backend.browser.actions import clicar
    selector = params.get("selector", "")
    if not selector:
        return {"success": False, "error": "Selector não informado"}
    
    page = _ensure_browser()
    clicar(page, selector)
    return {
        "success": True,
        "selector": selector,
        "message": f"Clicou em '{selector}'",
    }


@register_tool("browser_type")
def browser_type(params: dict, state: AgentState) -> dict[str, Any]:
    """Digita texto em um campo."""
    from backend.browser.actions import digitar
    selector = params.get("selector", "")
    text = params.get("text", params.get("texto", ""))
    secret = params.get("secret", False)
    
    if not selector:
        return {"success": False, "error": "Selector não informado"}
    
    page = _ensure_browser()
    digitar(page, selector, text, secret=secret)
    masked = "***" if secret else text[:50]
    return {
        "success": True,
        "selector": selector,
        "message": f"Digitou '{masked}' em '{selector}'",
    }


@register_tool("browser_wait_selector")
def browser_wait_selector(params: dict, state: AgentState) -> dict[str, Any]:
    """Aguarda um seletor aparecer na página."""
    from backend.browser.actions import esperar_selector
    selector = params.get("selector", "")
    timeout_ms = params.get("timeout_ms", 10000)
    
    if not selector:
        return {"success": False, "error": "Selector não informado"}
    
    page = _ensure_browser()
    esperar_selector(page, selector, timeout_ms=timeout_ms)
    return {
        "success": True,
        "selector": selector,
        "message": f"Selector '{selector}' encontrado",
    }


@register_tool("browser_press_key")
def browser_press_key(params: dict, state: AgentState) -> dict[str, Any]:
    """Pressiona uma tecla."""
    from backend.browser.actions import press_key
    key = params.get("key", "")
    if not key:
        return {"success": False, "error": "Tecla não informada"}
    
    page = _ensure_browser()
    press_key(page, key)
    return {
        "success": True,
        "key": key,
        "message": f"Pressionou tecla '{key}'",
    }


@register_tool("browser_wait")
def browser_wait(params: dict, state: AgentState) -> dict[str, Any]:
    """Aguarda N segundos."""
    from backend.browser.actions import wait_seconds
    seconds = params.get("seconds", 2)
    
    page = _ensure_browser()
    wait_seconds(page, seconds)
    return {
        "success": True,
        "message": f"Aguardou {seconds}s",
    }


@register_tool("browser_screenshot")
def browser_screenshot(params: dict, state: AgentState) -> dict[str, Any]:
    """Captura screenshot da página atual."""
    import base64
    
    page = _ensure_browser()
    path = params.get("path")
    
    if path:
        page.screenshot(path=path)
        return {
            "success": True,
            "path": path,
            "message": f"Screenshot salvo em {path}",
        }
    else:
        # Retorna base64 se não tiver path
        screenshot_bytes = page.screenshot()
        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        return {
            "success": True,
            "screenshot_base64": b64[:100] + "...",  # Truncar para log
            "message": "Screenshot capturado (base64)",
        }


@register_tool("browser_get_text")
def browser_get_text(params: dict, state: AgentState) -> dict[str, Any]:
    """Obtém o texto de um elemento da página."""
    selector = params.get("selector", "body")
    
    page = _ensure_browser()
    try:
        element = page.query_selector(selector)
        if element is None:
            return {"success": False, "error": f"Elemento '{selector}' não encontrado"}
        text = element.inner_text()
        return {
            "success": True,
            "text": text[:2000],  # Limitar tamanho
            "message": f"Texto de '{selector}': {text[:100]}...",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_tool("browser_close")
def browser_close(params: dict, state: AgentState) -> dict[str, Any]:
    """Encerra o browser."""
    shutdown_browser()
    return {
        "success": True,
        "message": "Browser encerrado",
    }
