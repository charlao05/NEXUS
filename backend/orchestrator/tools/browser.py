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

from orchestrator.nodes.act import register_browser_tool
from orchestrator.state import AgentState

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
        from browser.playwright_client import iniciar_navegador
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
            from browser.playwright_client import fechar_navegador
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

@register_browser_tool("browser_navigate")
def browser_navigate(params: dict, state: AgentState) -> dict[str, Any]:
    """Navega para uma URL."""
    from browser.actions import abrir_url
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


@register_browser_tool("browser_click")
def browser_click(params: dict, state: AgentState) -> dict[str, Any]:
    """Clica em um elemento da página."""
    from browser.actions import clicar
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


@register_browser_tool("browser_type")
def browser_type(params: dict, state: AgentState) -> dict[str, Any]:
    """Digita texto em um campo."""
    from browser.actions import digitar
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


@register_browser_tool("browser_wait_selector")
def browser_wait_selector(params: dict, state: AgentState) -> dict[str, Any]:
    """Aguarda um seletor aparecer na página."""
    from browser.actions import esperar_selector
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


@register_browser_tool("browser_press_key")
def browser_press_key(params: dict, state: AgentState) -> dict[str, Any]:
    """Pressiona uma tecla."""
    from browser.actions import press_key
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


@register_browser_tool("browser_wait")
def browser_wait(params: dict, state: AgentState) -> dict[str, Any]:
    """Aguarda N segundos."""
    from browser.actions import wait_seconds
    seconds = params.get("seconds", 2)
    
    page = _ensure_browser()
    wait_seconds(page, seconds)
    return {
        "success": True,
        "message": f"Aguardou {seconds}s",
    }


@register_browser_tool("browser_screenshot")
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


@register_browser_tool("browser_get_text")
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


@register_browser_tool("browser_close")
def browser_close(params: dict, state: AgentState) -> dict[str, Any]:
    """Encerra o browser."""
    shutdown_browser()
    return {
        "success": True,
        "message": "Browser encerrado",
    }


# ---------------------------------------------------------------------------
# Tools adicionais — Blueprint Comet
# ---------------------------------------------------------------------------

@register_browser_tool("browser_scroll")
def browser_scroll(params: dict, state: AgentState) -> dict[str, Any]:
    """Rola a página. params: {direction: up|down|left|right, amount?: pixels}"""
    from browser.actions import scroll
    direction = params.get("direction", "down")
    amount = params.get("amount", 500)

    page = _ensure_browser()
    scroll(page, direction, amount)
    return {
        "success": True,
        "message": f"Rolou {direction} por {amount}px",
    }


@register_browser_tool("browser_hover")
def browser_hover(params: dict, state: AgentState) -> dict[str, Any]:
    """Passa o mouse sobre um elemento."""
    from browser.actions import hover
    selector = params.get("selector", "")
    if not selector:
        return {"success": False, "error": "Selector não informado"}

    page = _ensure_browser()
    hover(page, selector)
    return {
        "success": True,
        "selector": selector,
        "message": f"Hover em '{selector}'",
    }


@register_browser_tool("browser_select_option")
def browser_select_option(params: dict, state: AgentState) -> dict[str, Any]:
    """Seleciona opção em dropdown <select>. params: {selector, value}"""
    from browser.actions import select_option
    selector = params.get("selector", "")
    value = params.get("value", "")
    if not selector or not value:
        return {"success": False, "error": "Selector e value são obrigatórios"}

    page = _ensure_browser()
    select_option(page, selector, value)
    return {
        "success": True,
        "selector": selector,
        "message": f"Selecionou '{value}' em '{selector}'",
    }


@register_browser_tool("browser_check_checkbox")
def browser_check_checkbox(params: dict, state: AgentState) -> dict[str, Any]:
    """Marca ou desmarca checkbox. params: {selector, checked?: true}"""
    from browser.actions import check_checkbox
    selector = params.get("selector", "")
    checked = params.get("checked", True)
    if not selector:
        return {"success": False, "error": "Selector não informado"}

    page = _ensure_browser()
    check_checkbox(page, selector, checked)
    action = "Marcou" if checked else "Desmarcou"
    return {
        "success": True,
        "selector": selector,
        "message": f"{action} checkbox '{selector}'",
    }


@register_browser_tool("browser_upload_file")
def browser_upload_file(params: dict, state: AgentState) -> dict[str, Any]:
    """Upload de arquivo. params: {selector, file_path}"""
    from browser.actions import upload_file
    selector = params.get("selector", "")
    file_path = params.get("file_path", "")
    if not selector or not file_path:
        return {"success": False, "error": "Selector e file_path são obrigatórios"}

    page = _ensure_browser()
    upload_file(page, selector, file_path)
    return {
        "success": True,
        "message": f"Arquivo '{file_path}' enviado via '{selector}'",
    }


@register_browser_tool("browser_submit_form")
def browser_submit_form(params: dict, state: AgentState) -> dict[str, Any]:
    """Submete formulário. params: {selector?: "form"}"""
    from browser.actions import submit_form
    selector = params.get("selector", "form")

    page = _ensure_browser()
    submit_form(page, selector)
    return {
        "success": True,
        "message": f"Formulário '{selector}' submetido",
    }


@register_browser_tool("browser_go_back")
def browser_go_back(params: dict, state: AgentState) -> dict[str, Any]:
    """Volta à página anterior (browser back)."""
    from browser.actions import go_back

    page = _ensure_browser()
    go_back(page)
    return {
        "success": True,
        "url": page.url,
        "message": f"Voltou para {page.url}",
    }


@register_browser_tool("browser_go_forward")
def browser_go_forward(params: dict, state: AgentState) -> dict[str, Any]:
    """Avança para a próxima página (browser forward)."""
    from browser.actions import go_forward

    page = _ensure_browser()
    go_forward(page)
    return {
        "success": True,
        "url": page.url,
        "message": f"Avançou para {page.url}",
    }


@register_browser_tool("browser_get_attribute")
def browser_get_attribute(params: dict, state: AgentState) -> dict[str, Any]:
    """Lê atributo de um elemento. params: {selector, attribute}"""
    from browser.actions import get_attribute
    selector = params.get("selector", "")
    attribute = params.get("attribute", "")
    if not selector or not attribute:
        return {"success": False, "error": "Selector e attribute são obrigatórios"}

    page = _ensure_browser()
    value = get_attribute(page, selector, attribute)
    return {
        "success": True,
        "value": value,
        "message": f"Atributo '{attribute}' de '{selector}': {value}",
    }


@register_browser_tool("browser_extract_table")
def browser_extract_table(params: dict, state: AgentState) -> dict[str, Any]:
    """Extrai dados de uma tabela HTML. params: {selector?: "table"}"""
    from browser.actions import extract_table
    selector = params.get("selector", "table")

    page = _ensure_browser()
    rows = extract_table(page, selector)
    return {
        "success": True,
        "rows": rows[:50],  # Limitar a 50 linhas
        "row_count": len(rows),
        "message": f"Tabela extraída: {len(rows)} linhas",
    }


@register_browser_tool("browser_find_by_text")
def browser_find_by_text(params: dict, state: AgentState) -> dict[str, Any]:
    """Encontra elemento pelo texto visível. params: {text, tag?: "*"}"""
    from browser.actions import find_element_by_text
    text = params.get("text", "")
    tag = params.get("tag", "*")
    if not text:
        return {"success": False, "error": "Texto não informado"}

    page = _ensure_browser()
    found_text = find_element_by_text(page, text, tag)
    if found_text:
        return {
            "success": True,
            "found_text": found_text[:200],
            "message": f"Elemento com texto '{text}' encontrado",
        }
    return {
        "success": False,
        "error": f"Elemento com texto '{text}' não encontrado",
    }


@register_browser_tool("browser_evaluate_js")
def browser_evaluate_js(params: dict, state: AgentState) -> dict[str, Any]:
    """Executa JavaScript na página. params: {expression}
    
    SEGURANÇA: Apenas expressões de leitura (consulta de dados).
    """
    from browser.actions import evaluate_js
    expression = params.get("expression", "")
    if not expression:
        return {"success": False, "error": "Expressão JS não informada"}

    # Bloquear expressões perigosas
    dangerous = ["fetch(", "XMLHttpRequest", "eval(", "Function(", "document.cookie"]
    if any(d in expression for d in dangerous):
        return {
            "success": False,
            "error": "Expressão JS bloqueada por segurança (contém operação proibida)",
        }

    page = _ensure_browser()
    result = evaluate_js(page, expression)
    result_str = str(result)[:2000]
    return {
        "success": True,
        "result": result_str,
        "message": f"JS executado: {result_str[:100]}",
    }


@register_browser_tool("browser_handle_dialog")
def browser_handle_dialog(params: dict, state: AgentState) -> dict[str, Any]:
    """Configura handler para diálogos (alert/confirm/prompt).
    params: {accept?: true, prompt_text?: ""}
    """
    from browser.actions import handle_dialog
    accept = params.get("accept", True)
    prompt_text = params.get("prompt_text", "")

    page = _ensure_browser()
    handle_dialog(page, accept, prompt_text)
    action = "aceitar" if accept else "rejeitar"
    return {
        "success": True,
        "message": f"Handler de diálogo configurado para {action}",
    }


@register_browser_tool("browser_drag_drop")
def browser_drag_drop(params: dict, state: AgentState) -> dict[str, Any]:
    """Arrasta um elemento para outro. params: {source, target}"""
    from browser.actions import drag_and_drop
    source = params.get("source", "")
    target = params.get("target", "")
    if not source or not target:
        return {"success": False, "error": "Source e target são obrigatórios"}

    page = _ensure_browser()
    drag_and_drop(page, source, target)
    return {
        "success": True,
        "message": f"Arrastou '{source}' para '{target}'",
    }


@register_browser_tool("browser_get_page_state")
def browser_get_page_state(params: dict, state: AgentState) -> dict[str, Any]:
    """Captura estado completo da página (percepção DOM estilo Steward).
    
    Retorna elementos interativos, URL, título, tipo da página.
    """
    from browser.perception import get_page_state

    page = _ensure_browser()
    page_state = get_page_state(page)

    # Remover raw_elements (não serializável para JSON)
    page_state.pop("raw_elements", None)

    return {
        "success": True,
        "page_state": page_state,
        "message": (
            f"Página: {page_state.get('title', '?')} | "
            f"Tipo: {page_state.get('page_type', '?')} | "
            f"{page_state.get('element_count', 0)} elementos"
        ),
    }
