"""
Camada de Percepção DOM — Estilo Steward/Agent-E.
==================================================
Extrai e comprime o DOM da página para contexto do LLM.

O LLM NÃO enxerga o DOM completo. Esta camada:
1. Captura elementos interativos (inputs, botões, links, selects)
2. Captura texto visível relevante
3. Filtra e comprime para caber no contexto
4. Formata como lista numerada para referência pelo agente

Formato de saída (estilo Steward):
    #1: button "Enviar" [selector=button.submit-btn]
    #2: input text, label "Email" [selector=#email]
    #3: select "Estado", options=["SP","RJ","ES"] [selector=#state]
    #4: link "Página inicial" → /home [selector=a.nav-home]
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Page

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Modelo de elemento interativo
# ---------------------------------------------------------------------------

@dataclass
class InteractiveElement:
    """Representa um elemento interativo da página."""
    index: int
    tag: str
    element_type: str  # button, input, select, link, textarea
    text: str
    selector: str
    attributes: dict[str, str] = field(default_factory=dict)
    options: list[str] = field(default_factory=list)
    is_visible: bool = True
    near_text: str = ""


# ---------------------------------------------------------------------------
# Extração de elementos interativos
# ---------------------------------------------------------------------------

_INTERACTIVE_SELECTORS = [
    "button",
    "input:not([type=hidden])",
    "textarea",
    "select",
    "a[href]",
    "[role=button]",
    "[role=link]",
    "[role=textbox]",
    "[role=combobox]",
    "[role=checkbox]",
    "[role=radio]",
    "[contenteditable=true]",
]


def extract_interactive_elements(page: Page, max_elements: int = 80) -> list[InteractiveElement]:
    """Extrai todos os elementos interativos visíveis da página.
    
    Args:
        page: Página Playwright ativa.
        max_elements: Limite máximo de elementos para evitar contexto muito grande.
    
    Returns:
        Lista de InteractiveElement ordenados por posição no DOM.
    """
    elements: list[InteractiveElement] = []
    seen_selectors: set[str] = set()
    idx = 0

    combined_selector = ", ".join(_INTERACTIVE_SELECTORS)

    try:
        raw_elements = page.query_selector_all(combined_selector)
    except Exception as e:
        logger.warning(f"Falha ao consultar DOM: {e}")
        return elements

    for el in raw_elements:
        if idx >= max_elements:
            break

        try:
            # Verificar visibilidade
            if not el.is_visible():
                continue

            tag = el.evaluate("el => el.tagName.toLowerCase()")
            el_type = el.get_attribute("type") or ""
            role = el.get_attribute("role") or ""

            # Montar seletor CSS único
            el_id = el.get_attribute("id")
            el_name = el.get_attribute("name")
            el_class = el.get_attribute("class") or ""

            if el_id:
                css_selector = f"#{el_id}"
            elif el_name:
                css_selector = f"{tag}[name='{el_name}']"
            elif el_class.strip():
                first_class = el_class.strip().split()[0]
                css_selector = f"{tag}.{first_class}"
            else:
                # Usar data-testid ou aria-label como fallback
                test_id = el.get_attribute("data-testid")
                aria = el.get_attribute("aria-label")
                if test_id:
                    css_selector = f"[data-testid='{test_id}']"
                elif aria:
                    css_selector = f"[aria-label='{aria}']"
                else:
                    css_selector = f"{tag}:nth-of-type({idx + 1})"

            # Evitar duplicatas
            if css_selector in seen_selectors:
                continue
            seen_selectors.add(css_selector)

            # Classificar tipo
            if tag == "button" or role == "button":
                element_type = "button"
            elif tag == "a":
                element_type = "link"
            elif tag == "select" or role == "combobox":
                element_type = "select"
            elif tag == "textarea" or role == "textbox":
                element_type = "textarea"
            elif tag == "input":
                if el_type in ("checkbox",):
                    element_type = "checkbox"
                elif el_type in ("radio",):
                    element_type = "radio"
                elif el_type in ("submit",):
                    element_type = "submit_button"
                elif el_type in ("file",):
                    element_type = "file_input"
                else:
                    element_type = f"input_{el_type or 'text'}"
            else:
                element_type = role or tag

            # Texto visível
            text = ""
            try:
                text = el.inner_text().strip()[:100]
            except Exception:
                pass
            if not text:
                text = (
                    el.get_attribute("aria-label")
                    or el.get_attribute("placeholder")
                    or el.get_attribute("title")
                    or el.get_attribute("value")
                    or ""
                )[:100]

            # Label associada
            label_text = ""
            if el_id:
                try:
                    label_el = page.query_selector(f"label[for='{el_id}']")
                    if label_el:
                        label_text = label_el.inner_text().strip()[:80]
                except Exception:
                    pass

            # Opções para <select>
            options: list[str] = []
            if element_type == "select":
                try:
                    opt_els = el.query_selector_all("option")
                    options = [o.inner_text().strip() for o in opt_els[:20]]
                except Exception:
                    pass

            # Atributos relevantes
            attrs: dict[str, str] = {}
            href = el.get_attribute("href")
            if href:
                attrs["href"] = href[:200]
            placeholder = el.get_attribute("placeholder")
            if placeholder:
                attrs["placeholder"] = placeholder
            value = el.get_attribute("value")
            if value and not el_type == "password":
                attrs["value"] = value[:50]
            required = el.get_attribute("required")
            if required is not None:
                attrs["required"] = "true"

            # Texto próximo (contexto)
            near = label_text or ""

            idx += 1
            elements.append(InteractiveElement(
                index=idx,
                tag=tag,
                element_type=element_type,
                text=text,
                selector=css_selector,
                attributes=attrs,
                options=options,
                near_text=near,
            ))

        except Exception as e:
            logger.debug(f"Erro ao processar elemento: {e}")
            continue

    logger.info(f"👁️ Percepção: {len(elements)} elementos interativos encontrados")
    return elements


# ---------------------------------------------------------------------------
# Formatação para contexto LLM (estilo Steward)
# ---------------------------------------------------------------------------

def format_elements_for_llm(elements: list[InteractiveElement]) -> str:
    """Formata elementos como lista numerada para o LLM.
    
    Formato:
        #1: button "Enviar" [selector=button.submit]
        #2: input_text, label "Email" [selector=#email] (required)
        #3: select "Estado", options=["SP","RJ"] [selector=#state]
    """
    if not elements:
        return "Nenhum elemento interativo encontrado na página."

    lines: list[str] = []
    for el in elements:
        parts = [f"#{el.index}: {el.element_type}"]

        if el.text:
            parts.append(f'"{el.text}"')
        if el.near_text:
            parts.append(f'label "{el.near_text}"')
        if el.options:
            opts_str = str(el.options[:10])
            parts.append(f"options={opts_str}")
        if el.attributes.get("href"):
            parts.append(f'→ {el.attributes["href"][:80]}')
        if el.attributes.get("placeholder"):
            parts.append(f'placeholder="{el.attributes["placeholder"]}"')
        if el.attributes.get("required"):
            parts.append("(obrigatório)")

        parts.append(f"[selector={el.selector}]")
        lines.append(" ".join(parts))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Estado completo da página (percepção Comet)
# ---------------------------------------------------------------------------

def get_page_state(page: Page) -> dict[str, Any]:
    """Captura estado completo da página para o agente.
    
    Retorna dict com:
        - url: URL atual
        - title: Título da página
        - visible_text: Texto visível resumido (max 2000 chars)
        - interactive_elements: Lista formatada de elementos interativos
        - element_count: Quantidade de elementos
        - has_form: Se a página tem formulários
        - page_type: Tipo detectado (form, table, article, portal, login, etc.)
    """
    try:
        url = page.url
        title = page.title()

        # Texto visível (resumido)
        visible_text = ""
        try:
            body = page.query_selector("body")
            if body:
                raw_text = body.inner_text()
                # Limpar espaços múltiplos e limitar
                visible_text = re.sub(r'\s+', ' ', raw_text).strip()[:2000]
        except Exception:
            pass

        # Elementos interativos
        elements = extract_interactive_elements(page)
        formatted = format_elements_for_llm(elements)

        # Detectar tipo de página
        has_form = bool(page.query_selector("form"))
        has_table = bool(page.query_selector("table"))
        has_login = any(
            el.element_type in ("input_password",) for el in elements
        ) or bool(page.query_selector("[type=password]"))

        if has_login:
            page_type = "login"
        elif has_form:
            page_type = "form"
        elif has_table:
            page_type = "table"
        else:
            page_type = "content"

        return {
            "url": url,
            "title": title,
            "visible_text": visible_text,
            "interactive_elements": formatted,
            "element_count": len(elements),
            "has_form": has_form,
            "has_table": has_table,
            "page_type": page_type,
            "raw_elements": elements,  # Para uso programático
        }

    except Exception as e:
        logger.error(f"Erro na percepção da página: {e}")
        return {
            "url": page.url if page else "unknown",
            "title": "",
            "visible_text": "",
            "interactive_elements": "Erro ao capturar estado da página.",
            "element_count": 0,
            "has_form": False,
            "has_table": False,
            "page_type": "error",
            "raw_elements": [],
        }


def get_compact_observation(page: Page) -> str:
    """Retorna observação compacta da página para o loop ReAct.
    
    Formato conciso para uso entre iterações do agente.
    """
    state = get_page_state(page)
    lines = [
        f"📍 URL: {state['url']}",
        f"📄 Título: {state['title']}",
        f"📋 Tipo: {state['page_type']}",
        f"🔢 {state['element_count']} elementos interativos",
        "",
        "Elementos:",
        state["interactive_elements"],
    ]

    # Adicionar texto visível resumido se pouco elementos
    if state["element_count"] < 5 and state["visible_text"]:
        lines.insert(4, f"\nTexto: {state['visible_text'][:500]}")

    return "\n".join(lines)
