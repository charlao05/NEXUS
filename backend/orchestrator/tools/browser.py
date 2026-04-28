"""
Browser tools para o orquestrador LangGraph.
=============================================
Registra ferramentas de automacao de navegador. Cada tool delega
para a infraestrutura Playwright em backend/browser/, mas usa:

- BrowserPool: contexto isolado por usuario (sem singleton compartilhado)
- DomainCircuitBreaker: corta calls quando um dominio esta fora ou bloqueando
- Retry transparente em falhas transientes (Timeout, conexao)
- AutomationLogger: audit log estruturado em todas as acoes

Cada tool segue o protocolo do act_node:
    fn(params: dict, state: AgentState) -> dict
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable
from urllib.parse import urlparse

from orchestrator.nodes.act import register_browser_tool
from orchestrator.state import AgentState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers — ciclo de vida da sessao via BrowserPool
# ---------------------------------------------------------------------------

def _get_user_id(state: AgentState) -> int:
    """Extrai user_id do state com fallback seguro."""
    uid = state.get("user_id", 0) if isinstance(state, dict) else 0
    return int(uid) if uid else 0


def _get_task_id(state: AgentState) -> str:
    """Extrai task_id do state com fallback seguro."""
    return state.get("task_id", "no_task") if isinstance(state, dict) else "no_task"


def _ensure_session(state: AgentState):
    """Adquire sessao do pool para o usuario atual.

    Idempotente: se ja existe sessao para o user, retorna ela.
    """
    from browser.pool import BrowserPool

    pool = BrowserPool.get_instance()
    user_id = _get_user_id(state)
    task_id = _get_task_id(state)

    return pool.acquire(user_id=user_id, task_id=task_id)


def _get_page(state: AgentState):
    """Retorna a Page da sessao isolada do usuario."""
    session = _ensure_session(state)
    return session.page


def _current_domain(state: AgentState) -> str:
    """Retorna dominio atual da pagina (ou string vazia)."""
    try:
        page = _get_page(state)
        return urlparse(page.url).netloc.lower()
    except Exception:
        return ""


def shutdown_browser(user_id: int = 0, close: bool = True) -> None:
    """Encerra a sessao de browser de um usuario (compat layer).

    Mantem assinatura legada para compatibilidade com graph.py.
    Se user_id=0, fecha o pool inteiro.
    """
    from browser.pool import BrowserPool

    pool = BrowserPool.get_instance()
    if user_id and user_id > 0:
        pool.release(user_id, save_session=True, close=close)
    else:
        pool.shutdown()
    logger.info(f"shutdown_browser chamado | user={user_id} close={close}")


# ---------------------------------------------------------------------------
# Wrapper principal — circuit breaker + retry + audit log
# ---------------------------------------------------------------------------

def _execute(
    state: AgentState,
    tool_name: str,
    fn: Callable[[Any], dict[str, Any]],
    *,
    target: str = "",
    risk: str = "low",
    check_circuit_url: str = "",
) -> dict[str, Any]:
    """Executa acao de browser com circuit breaker, retry e audit log.

    Args:
        state: AgentState do orquestrador.
        tool_name: nome da tool (para logging).
        fn: funcao que recebe a Page e retorna o dict de resultado.
        target: descricao do alvo (selector, url, etc) para audit.
        risk: nivel de risco (low/medium/high/critical).
        check_circuit_url: se passada, verifica circuit breaker antes
                          de executar (uso primario: browser_navigate).

    Returns:
        Dict com {success, ...} no padrao das tools.
    """
    from browser.circuit_breaker import CircuitOpenError, DomainCircuitBreaker
    from utils.automation_logger import AutomationLogger

    breaker = DomainCircuitBreaker.get_instance()
    user_id = _get_user_id(state)

    # 1. Circuit breaker check (apenas em navigate)
    if check_circuit_url:
        try:
            breaker.check(check_circuit_url)
        except CircuitOpenError as e:
            AutomationLogger.action_blocked(
                tool=tool_name,
                reason=f"Circuit OPEN para {e.domain} (retry em {e.retry_in_seconds}s)",
                risk="high",
                target=check_circuit_url,
            )
            return {
                "success": False,
                "error": str(e),
                "circuit_open": True,
                "retry_in_seconds": e.retry_in_seconds,
                "message": (
                    f"Site '{e.domain}' indisponivel ou bloqueando. "
                    f"Tentaremos novamente em {e.retry_in_seconds}s."
                ),
            }

    # 2. Garantir sessao
    try:
        page = _get_page(state)
    except Exception as e:
        AutomationLogger.action_failed(
            tool=tool_name,
            error=f"Falha ao obter sessao do pool: {e}",
            risk="high",
            target=target,
        )
        return {
            "success": False,
            "error": f"Sessao de browser indisponivel: {e}",
        }

    # 3. Executar com retry transparente
    from browser.actions import with_retry

    @with_retry(max_attempts=3, base_delay=0.5, max_delay=4.0)
    def _do() -> dict[str, Any]:
        return fn(page)

    start = time.time()
    domain_for_breaker = check_circuit_url or _current_domain(state)

    try:
        result = _do()
        duration_ms = int((time.time() - start) * 1000)

        AutomationLogger.action_executed(
            tool=tool_name,
            risk=risk,
            target=target,
            success=bool(result.get("success", True)),
            duration_ms=duration_ms,
        )

        # Sucesso vale para circuit breaker (apenas em navigate ou apos navigate)
        if domain_for_breaker:
            breaker.record_success(domain_for_breaker)

        # Atualizar dominio na sessao (depois de navigate)
        if check_circuit_url:
            try:
                from browser.pool import BrowserPool
                session = BrowserPool.get_instance().get_session(user_id)
                if session:
                    session.domain = urlparse(check_circuit_url).netloc.lower()
            except Exception:
                pass

        return result

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)

        AutomationLogger.action_failed(
            tool=tool_name,
            error=str(e),
            risk="medium" if risk == "low" else risk,
            target=target,
            duration_ms=duration_ms,
        )

        if domain_for_breaker:
            breaker.record_failure(domain_for_breaker)

        return {
            "success": False,
            "error": str(e),
            "tool": tool_name,
        }


# ---------------------------------------------------------------------------
# Tools registradas no act_node
# ---------------------------------------------------------------------------

@register_browser_tool("browser_navigate")
def browser_navigate(params: dict, state: AgentState) -> dict[str, Any]:
    """Navega para uma URL."""
    url = params.get("url", "")
    if not url:
        return {"success": False, "error": "URL nao informada"}

    def _fn(page):
        from browser.actions import abrir_url
        abrir_url(page, url)
        title = page.title()
        return {
            "success": True,
            "url": url,
            "title": title,
            "message": f"Navegou para {url} — titulo: {title}",
        }

    return _execute(
        state, "browser_navigate", _fn,
        target=url, risk="medium", check_circuit_url=url,
    )


@register_browser_tool("browser_click")
def browser_click(params: dict, state: AgentState) -> dict[str, Any]:
    """Clica em um elemento da pagina."""
    selector = params.get("selector", "")
    if not selector:
        return {"success": False, "error": "Selector nao informado"}

    def _fn(page):
        from browser.actions import clicar
        clicar(page, selector)
        return {"success": True, "selector": selector, "message": f"Clicou em '{selector}'"}

    return _execute(state, "browser_click", _fn, target=selector, risk="low")


@register_browser_tool("browser_type")
def browser_type(params: dict, state: AgentState) -> dict[str, Any]:
    """Digita texto em um campo."""
    selector = params.get("selector", "")
    text = params.get("text", params.get("texto", ""))
    secret = params.get("secret", False)

    if not selector:
        return {"success": False, "error": "Selector nao informado"}

    def _fn(page):
        from browser.actions import digitar
        digitar(page, selector, text, secret=secret)
        masked = "***" if secret else text[:50]
        return {"success": True, "selector": selector, "message": f"Digitou '{masked}' em '{selector}'"}

    return _execute(
        state, "browser_type", _fn,
        target=selector, risk="medium" if secret else "low",
    )


@register_browser_tool("browser_wait_selector")
def browser_wait_selector(params: dict, state: AgentState) -> dict[str, Any]:
    """Aguarda um seletor aparecer na pagina."""
    selector = params.get("selector", "")
    timeout_ms = params.get("timeout_ms", 10000)

    if not selector:
        return {"success": False, "error": "Selector nao informado"}

    def _fn(page):
        from browser.actions import esperar_selector
        esperar_selector(page, selector, timeout_ms=timeout_ms)
        return {"success": True, "selector": selector, "message": f"Selector '{selector}' encontrado"}

    return _execute(state, "browser_wait_selector", _fn, target=selector, risk="low")


@register_browser_tool("browser_press_key")
def browser_press_key(params: dict, state: AgentState) -> dict[str, Any]:
    """Pressiona uma tecla."""
    key = params.get("key", "")
    if not key:
        return {"success": False, "error": "Tecla nao informada"}

    def _fn(page):
        from browser.actions import press_key
        press_key(page, key)
        return {"success": True, "key": key, "message": f"Pressionou tecla '{key}'"}

    return _execute(state, "browser_press_key", _fn, target=key, risk="low")


@register_browser_tool("browser_wait")
def browser_wait(params: dict, state: AgentState) -> dict[str, Any]:
    """Aguarda N segundos."""
    seconds = params.get("seconds", 2)

    def _fn(page):
        from browser.actions import wait_seconds
        wait_seconds(page, seconds)
        return {"success": True, "message": f"Aguardou {seconds}s"}

    return _execute(state, "browser_wait", _fn, target=str(seconds), risk="low")


@register_browser_tool("browser_screenshot")
def browser_screenshot(params: dict, state: AgentState) -> dict[str, Any]:
    """Captura screenshot da pagina atual."""
    import base64

    def _fn(page):
        path = params.get("path")
        if path:
            page.screenshot(path=path)
            return {"success": True, "path": path, "message": f"Screenshot salvo em {path}"}
        else:
            screenshot_bytes = page.screenshot()
            b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            return {
                "success": True,
                "screenshot_base64": b64[:100] + "...",
                "message": "Screenshot capturado (base64)",
            }

    return _execute(state, "browser_screenshot", _fn, risk="low")


@register_browser_tool("browser_get_text")
def browser_get_text(params: dict, state: AgentState) -> dict[str, Any]:
    """Obtem o texto de um elemento da pagina."""
    selector = params.get("selector", "body")

    def _fn(page):
        element = page.query_selector(selector)
        if element is None:
            return {"success": False, "error": f"Elemento '{selector}' nao encontrado"}
        text = element.inner_text()
        return {
            "success": True,
            "text": text[:2000],
            "message": f"Texto de '{selector}': {text[:100]}...",
        }

    return _execute(state, "browser_get_text", _fn, target=selector, risk="low")


@register_browser_tool("browser_close")
def browser_close(params: dict, state: AgentState) -> dict[str, Any]:
    """Encerra a sessao do usuario (libera ao pool, salva cookies)."""
    user_id = _get_user_id(state)
    try:
        from browser.pool import BrowserPool
        from utils.automation_logger import AutomationLogger
        pool = BrowserPool.get_instance()
        pool.release(user_id, save_session=True, close=True)
        AutomationLogger.session_released(closed=True)
        return {"success": True, "message": "Sessao de browser encerrada"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Tools adicionais — Blueprint Comet
# ---------------------------------------------------------------------------

@register_browser_tool("browser_scroll")
def browser_scroll(params: dict, state: AgentState) -> dict[str, Any]:
    """Rola a pagina."""
    direction = params.get("direction", "down")
    amount = params.get("amount", 500)

    def _fn(page):
        from browser.actions import scroll
        scroll(page, direction, amount)
        return {"success": True, "message": f"Rolou {direction} por {amount}px"}

    return _execute(state, "browser_scroll", _fn, target=direction, risk="low")


@register_browser_tool("browser_hover")
def browser_hover(params: dict, state: AgentState) -> dict[str, Any]:
    """Passa o mouse sobre um elemento."""
    selector = params.get("selector", "")
    if not selector:
        return {"success": False, "error": "Selector nao informado"}

    def _fn(page):
        from browser.actions import hover
        hover(page, selector)
        return {"success": True, "selector": selector, "message": f"Hover em '{selector}'"}

    return _execute(state, "browser_hover", _fn, target=selector, risk="low")


@register_browser_tool("browser_select_option")
def browser_select_option(params: dict, state: AgentState) -> dict[str, Any]:
    """Seleciona opcao em dropdown <select>."""
    selector = params.get("selector", "")
    value = params.get("value", "")
    if not selector or not value:
        return {"success": False, "error": "Selector e value sao obrigatorios"}

    def _fn(page):
        from browser.actions import select_option
        select_option(page, selector, value)
        return {"success": True, "selector": selector, "message": f"Selecionou '{value}' em '{selector}'"}

    return _execute(state, "browser_select_option", _fn, target=selector, risk="low")


@register_browser_tool("browser_check_checkbox")
def browser_check_checkbox(params: dict, state: AgentState) -> dict[str, Any]:
    """Marca ou desmarca checkbox."""
    selector = params.get("selector", "")
    checked = params.get("checked", True)
    if not selector:
        return {"success": False, "error": "Selector nao informado"}

    def _fn(page):
        from browser.actions import check_checkbox
        check_checkbox(page, selector, checked)
        action = "Marcou" if checked else "Desmarcou"
        return {"success": True, "selector": selector, "message": f"{action} checkbox '{selector}'"}

    return _execute(state, "browser_check_checkbox", _fn, target=selector, risk="low")


@register_browser_tool("browser_upload_file")
def browser_upload_file(params: dict, state: AgentState) -> dict[str, Any]:
    """Upload de arquivo."""
    selector = params.get("selector", "")
    file_path = params.get("file_path", "")
    if not selector or not file_path:
        return {"success": False, "error": "Selector e file_path sao obrigatorios"}

    def _fn(page):
        from browser.actions import upload_file
        upload_file(page, selector, file_path)
        return {"success": True, "message": f"Arquivo '{file_path}' enviado via '{selector}'"}

    return _execute(state, "browser_upload_file", _fn, target=file_path, risk="medium")


@register_browser_tool("browser_submit_form")
def browser_submit_form(params: dict, state: AgentState) -> dict[str, Any]:
    """Submete formulario."""
    selector = params.get("selector", "form")

    def _fn(page):
        from browser.actions import submit_form
        submit_form(page, selector)
        return {"success": True, "message": f"Formulario '{selector}' submetido"}

    return _execute(state, "browser_submit_form", _fn, target=selector, risk="medium")


@register_browser_tool("browser_go_back")
def browser_go_back(params: dict, state: AgentState) -> dict[str, Any]:
    """Volta a pagina anterior."""
    def _fn(page):
        from browser.actions import go_back
        go_back(page)
        return {"success": True, "url": page.url, "message": f"Voltou para {page.url}"}

    return _execute(state, "browser_go_back", _fn, risk="low")


@register_browser_tool("browser_go_forward")
def browser_go_forward(params: dict, state: AgentState) -> dict[str, Any]:
    """Avanca para a proxima pagina."""
    def _fn(page):
        from browser.actions import go_forward
        go_forward(page)
        return {"success": True, "url": page.url, "message": f"Avancou para {page.url}"}

    return _execute(state, "browser_go_forward", _fn, risk="low")


@register_browser_tool("browser_get_attribute")
def browser_get_attribute(params: dict, state: AgentState) -> dict[str, Any]:
    """Le atributo de um elemento."""
    selector = params.get("selector", "")
    attribute = params.get("attribute", "")
    if not selector or not attribute:
        return {"success": False, "error": "Selector e attribute sao obrigatorios"}

    def _fn(page):
        from browser.actions import get_attribute
        value = get_attribute(page, selector, attribute)
        return {
            "success": True,
            "value": value,
            "message": f"Atributo '{attribute}' de '{selector}': {value}",
        }

    return _execute(state, "browser_get_attribute", _fn, target=selector, risk="low")


@register_browser_tool("browser_extract_table")
def browser_extract_table(params: dict, state: AgentState) -> dict[str, Any]:
    """Extrai dados de uma tabela HTML."""
    selector = params.get("selector", "table")

    def _fn(page):
        from browser.actions import extract_table
        rows = extract_table(page, selector)
        return {
            "success": True,
            "rows": rows[:50],
            "row_count": len(rows),
            "message": f"Tabela extraida: {len(rows)} linhas",
        }

    return _execute(state, "browser_extract_table", _fn, target=selector, risk="low")


@register_browser_tool("browser_find_by_text")
def browser_find_by_text(params: dict, state: AgentState) -> dict[str, Any]:
    """Encontra elemento pelo texto visivel."""
    text = params.get("text", "")
    tag = params.get("tag", "*")
    if not text:
        return {"success": False, "error": "Texto nao informado"}

    def _fn(page):
        from browser.actions import find_element_by_text
        found_text = find_element_by_text(page, text, tag)
        if found_text:
            return {
                "success": True,
                "found_text": found_text[:200],
                "message": f"Elemento com texto '{text}' encontrado",
            }
        return {"success": False, "error": f"Elemento com texto '{text}' nao encontrado"}

    return _execute(state, "browser_find_by_text", _fn, target=text, risk="low")


@register_browser_tool("browser_evaluate_js")
def browser_evaluate_js(params: dict, state: AgentState) -> dict[str, Any]:
    """Executa JavaScript na pagina (apenas leitura)."""
    expression = params.get("expression", "")
    if not expression:
        return {"success": False, "error": "Expressao JS nao informada"}

    dangerous = ["fetch(", "XMLHttpRequest", "eval(", "Function(", "document.cookie"]
    if any(d in expression for d in dangerous):
        from utils.automation_logger import AutomationLogger
        AutomationLogger.action_blocked(
            tool="browser_evaluate_js",
            reason="Expressao JS contem operacao proibida",
            risk="critical",
            target=expression[:80],
        )
        return {
            "success": False,
            "error": "Expressao JS bloqueada por seguranca (contem operacao proibida)",
        }

    def _fn(page):
        from browser.actions import evaluate_js
        result = evaluate_js(page, expression)
        result_str = str(result)[:2000]
        return {"success": True, "result": result_str, "message": f"JS executado: {result_str[:100]}"}

    return _execute(state, "browser_evaluate_js", _fn, target=expression[:80], risk="medium")


@register_browser_tool("browser_handle_dialog")
def browser_handle_dialog(params: dict, state: AgentState) -> dict[str, Any]:
    """Configura handler para dialogos."""
    accept = params.get("accept", True)
    prompt_text = params.get("prompt_text", "")

    def _fn(page):
        from browser.actions import handle_dialog
        handle_dialog(page, accept, prompt_text)
        action = "aceitar" if accept else "rejeitar"
        return {"success": True, "message": f"Handler de dialogo configurado para {action}"}

    return _execute(state, "browser_handle_dialog", _fn, risk="low")


@register_browser_tool("browser_drag_drop")
def browser_drag_drop(params: dict, state: AgentState) -> dict[str, Any]:
    """Arrasta um elemento para outro."""
    source = params.get("source", "")
    target = params.get("target", "")
    if not source or not target:
        return {"success": False, "error": "Source e target sao obrigatorios"}

    def _fn(page):
        from browser.actions import drag_and_drop
        drag_and_drop(page, source, target)
        return {"success": True, "message": f"Arrastou '{source}' para '{target}'"}

    return _execute(state, "browser_drag_drop", _fn, target=f"{source}->{target}", risk="low")


@register_browser_tool("browser_get_page_state")
def browser_get_page_state(params: dict, state: AgentState) -> dict[str, Any]:
    """Captura estado completo da pagina (percepcao DOM estilo Steward)."""
    def _fn(page):
        from browser.perception import get_page_state
        page_state = get_page_state(page)
        page_state.pop("raw_elements", None)
        return {
            "success": True,
            "page_state": page_state,
            "message": (
                f"Pagina: {page_state.get('title', '?')} | "
                f"Tipo: {page_state.get('page_type', '?')} | "
                f"{page_state.get('element_count', 0)} elementos"
            ),
        }

    return _execute(state, "browser_get_page_state", _fn, risk="low")
