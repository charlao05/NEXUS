"""Ações primitivas utilizadas pelos agentes para manipular páginas.

Vocabulário completo do browser agent seguindo o Blueprint Comet:
- Navegação: abrir_url, scroll, go_back, go_forward
- Interação: clicar, digitar, type_text, press_key, hover
- Formulários: select_option, check_checkbox, upload_file, submit_form
- Leitura: get_text, get_attribute, get_page_content, extract_table, find_element_by_text
- Espera: esperar_selector, wait_seconds
- Avançado: evaluate_js, handle_dialog, drag_and_drop
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

try:
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..utils.logging_utils import get_logger

logger = get_logger("browser.actions")


# ---------------------------------------------------------------------------
# Navegação
# ---------------------------------------------------------------------------

def abrir_url(page: Page, url: str) -> None:
    logger.info("Abrindo URL: %s", url)
    try:
        page.goto(url, wait_until="load")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Falha ao abrir URL {url}: {exc}") from exc


def scroll(page: Page, direction: str = "down", amount: int = 500) -> None:
    """Rola a página na direção especificada.
    
    Args:
        direction: 'up', 'down', 'left', 'right'
        amount: pixels para rolar (default 500)
    """
    logger.info("Scroll %s por %dpx", direction, amount)
    try:
        deltas = {
            "down": (0, amount),
            "up": (0, -amount),
            "right": (amount, 0),
            "left": (-amount, 0),
        }
        dx, dy = deltas.get(direction.lower(), (0, amount))
        page.mouse.wheel(dx, dy)
    except Exception as exc:
        raise RuntimeError(f"Falha ao rolar {direction}: {exc}") from exc


def go_back(page: Page) -> None:
    """Volta à página anterior."""
    logger.info("Navegando para trás")
    try:
        page.go_back()
    except Exception as exc:
        raise RuntimeError(f"Falha ao voltar: {exc}") from exc


def go_forward(page: Page) -> None:
    """Avança para a próxima página."""
    logger.info("Navegando para frente")
    try:
        page.go_forward()
    except Exception as exc:
        raise RuntimeError(f"Falha ao avançar: {exc}") from exc


# ---------------------------------------------------------------------------
# Interação básica
# ---------------------------------------------------------------------------

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


def type_text(page: Page, selector: str, text: str) -> None:
    """Digita texto em um campo (alias para digitar)."""
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


def hover(page: Page, selector: str) -> None:
    """Passa o mouse sobre um elemento (hover)."""
    logger.info("Hover em: %s", selector)
    try:
        page.hover(selector)
    except Exception as exc:
        raise RuntimeError(f"Falha ao hover em {selector}: {exc}") from exc


# ---------------------------------------------------------------------------
# Formulários
# ---------------------------------------------------------------------------

def select_option(page: Page, selector: str, value: str) -> None:
    """Seleciona opção em um <select> pelo value, label ou texto visível."""
    logger.info("Selecionando '%s' em %s", value, selector)
    try:
        page.select_option(selector, value)
    except Exception:
        # Tenta por label se value falhar
        try:
            page.select_option(selector, label=value)
        except Exception as exc:
            raise RuntimeError(f"Falha ao selecionar '{value}' em {selector}: {exc}") from exc


def check_checkbox(page: Page, selector: str, checked: bool = True) -> None:
    """Marca ou desmarca um checkbox."""
    action = "Marcando" if checked else "Desmarcando"
    logger.info("%s checkbox: %s", action, selector)
    try:
        if checked:
            page.check(selector)
        else:
            page.uncheck(selector)
    except Exception as exc:
        raise RuntimeError(f"Falha ao {'marcar' if checked else 'desmarcar'} {selector}: {exc}") from exc


def upload_file(page: Page, selector: str, file_path: str) -> None:
    """Upload de arquivo via input[type=file]."""
    logger.info("Upload de arquivo: %s -> %s", file_path, selector)
    try:
        page.set_input_files(selector, file_path)
    except Exception as exc:
        raise RuntimeError(f"Falha no upload de {file_path}: {exc}") from exc


def submit_form(page: Page, selector: str = "form") -> None:
    """Submete um formulário (pressiona Enter ou clica no submit)."""
    logger.info("Submetendo formulário: %s", selector)
    try:
        submit_btn = page.query_selector(f"{selector} [type=submit], {selector} button[type=submit]")
        if submit_btn:
            submit_btn.click()
        else:
            page.keyboard.press("Enter")
    except Exception as exc:
        raise RuntimeError(f"Falha ao submeter formulário {selector}: {exc}") from exc


# ---------------------------------------------------------------------------
# Leitura / Extração
# ---------------------------------------------------------------------------

def get_text(page: Page, selector: str = "body") -> str:
    """Obtém texto visível de um elemento."""
    logger.info("Obtendo texto de: %s", selector)
    try:
        el = page.query_selector(selector)
        if el is None:
            return ""
        return el.inner_text()
    except Exception as exc:
        raise RuntimeError(f"Falha ao obter texto de {selector}: {exc}") from exc


def get_attribute(page: Page, selector: str, attribute: str) -> str | None:
    """Lê um atributo de um elemento (href, src, value, etc.)."""
    logger.info("Obtendo atributo '%s' de: %s", attribute, selector)
    try:
        el = page.query_selector(selector)
        if el is None:
            return None
        return el.get_attribute(attribute)
    except Exception as exc:
        raise RuntimeError(f"Falha ao obter atributo {attribute} de {selector}: {exc}") from exc


def get_page_content(page: Page) -> str:
    """Retorna HTML da página (limitado a 50k chars para contexto LLM)."""
    logger.info("Obtendo conteúdo HTML da página")
    try:
        content = page.content()
        return content[:50_000]
    except Exception as exc:
        raise RuntimeError(f"Falha ao obter conteúdo da página: {exc}") from exc


def extract_table(page: Page, selector: str = "table") -> list[list[str]]:
    """Extrai dados de uma tabela HTML como lista de listas.
    
    Retorna lista de linhas, cada linha é lista de células.
    Primeira linha = cabeçalho se existir <thead>.
    """
    logger.info("Extraindo tabela: %s", selector)
    try:
        rows: list[list[str]] = []
        # Cabeçalho
        headers = page.query_selector_all(f"{selector} thead th")
        if headers:
            rows.append([h.inner_text().strip() for h in headers])
        # Corpo
        body_rows = page.query_selector_all(f"{selector} tbody tr")
        if not body_rows:
            body_rows = page.query_selector_all(f"{selector} tr")
        for row in body_rows[:100]:  # Limitar a 100 linhas
            cells = row.query_selector_all("td, th")
            rows.append([c.inner_text().strip() for c in cells])
        return rows
    except Exception as exc:
        raise RuntimeError(f"Falha ao extrair tabela {selector}: {exc}") from exc


def find_element_by_text(page: Page, text: str, tag: str = "*") -> str | None:
    """Encontra elemento pelo texto visível e retorna seletor XPath.
    
    Útil quando não se sabe o seletor CSS exato.
    """
    logger.info("Procurando elemento com texto: '%s'", text)
    try:
        el = page.locator(f"{tag}:has-text('{text}')").first
        if el.count() > 0:
            # Retorna o inner_text para confirmação
            return el.inner_text()
        return None
    except Exception as exc:
        raise RuntimeError(f"Falha ao buscar texto '{text}': {exc}") from exc


# ---------------------------------------------------------------------------
# Espera
# ---------------------------------------------------------------------------

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


def wait_seconds(page: Page, seconds: int) -> None:
    """Aguarda N segundos."""
    logger.info("Aguardando %d segundo(s)", seconds)
    try:
        page.wait_for_timeout(seconds * 1000)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Erro ao aguardar {seconds} segundos: {exc}") from exc


# ---------------------------------------------------------------------------
# Avançado
# ---------------------------------------------------------------------------

def evaluate_js(page: Page, expression: str) -> Any:
    """Executa JavaScript na página e retorna resultado.
    
    SEGURANÇA: Apenas leitura de dados. Não usar para modificar DOM
    de forma destrutiva.
    """
    logger.info("Executando JS: %s", expression[:100])
    try:
        return page.evaluate(expression)
    except Exception as exc:
        raise RuntimeError(f"Falha ao executar JS: {exc}") from exc


def handle_dialog(page: Page, accept: bool = True, prompt_text: str = "") -> None:
    """Configura handler para diálogos (alert, confirm, prompt).
    
    Deve ser chamado ANTES da ação que dispara o diálogo.
    """
    logger.info("Configurando dialog handler: accept=%s", accept)
    def _handler(dialog):
        if accept:
            if prompt_text and dialog.type == "prompt":
                dialog.accept(prompt_text)
            else:
                dialog.accept()
        else:
            dialog.dismiss()
    page.on("dialog", _handler)


def drag_and_drop(page: Page, source: str, target: str) -> None:
    """Arrasta um elemento de source para target."""
    logger.info("Drag & drop: %s -> %s", source, target)
    try:
        page.drag_and_drop(source, target)
    except Exception as exc:
        raise RuntimeError(f"Falha no drag & drop de {source} para {target}: {exc}") from exc
