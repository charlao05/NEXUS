# src/browser/playwright_client.py

"""
Camada de integração com o Playwright (modo síncrono).

Responsável por:
- iniciar o Playwright e o navegador
- devolver uma page pronta para uso
- fechar tudo com segurança no final

STEALTH:
- Aplica playwright-stealth para mascarar navigator.webdriver
- Configura user-agent, viewport, locale e timezone realistas
- Passa args de Chromium que reduzem fingerprinting de automação
"""

from __future__ import annotations

import os
import random
import time
from typing import Any, Optional, Tuple

from playwright.sync_api import sync_playwright

try:
    from utils.logging_utils import get_logger
except ImportError:
    from utils.logging_utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Perfis realistas de navegador (rotação a cada launch)
# ---------------------------------------------------------------------------

_REALISTIC_USER_AGENTS: list[str] = [
    # Chrome 134 – Windows 10 (março 2026)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.89 Safari/537.36",
    # Chrome 133 – Windows 10
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.127 Safari/537.36",
    # Chrome 134 – Windows 11
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.89 Safari/537.36",
    # Edge 133 – Windows 10
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.127 Safari/537.36 Edg/133.0.3065.92",
]

_REALISTIC_VIEWPORTS: list[dict[str, int]] = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]

# Args de Chromium que reduzem sinais de automação
_STEALTH_CHROMIUM_ARGS: list[str] = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-component-extensions-with-background-pages",
    "--disable-background-networking",
    "--disable-dev-shm-usage",
    "--disable-popup-blocking",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-setuid-sandbox",
]


def iniciar_navegador(
    browser_name: Optional[str] = None,
    headless: Optional[bool] = None,
) -> Tuple[Any, Any, Any]:
    """
    Inicia o Playwright e um navegador (chromium/firefox/webkit)
    e devolve (playwright, browser, page).

    Aplica medidas anti-detecção automaticamente:
    1. Args de Chromium que removem flags de automação
    2. User-agent realista (rotação aleatória)
    3. Viewport de resolução comum
    4. Locale pt-BR e timezone America/Sao_Paulo
    5. playwright-stealth patches (navigator.webdriver, etc.)

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

    # --- Camada 1: args de launch (Chromium only) ---
    launch_opts: dict[str, Any] = {"headless": headless}
    _using_real_chrome = False

    if browser_name.lower() not in ("firefox", "webkit"):
        launch_opts["args"] = list(_STEALTH_CHROMIUM_ARGS)
        # Ignora o arg default --enable-automation que o Chromium injeta
        launch_opts["ignore_default_args"] = ["--enable-automation"]

    if browser_name.lower() == "firefox":
        browser = p.firefox.launch(**launch_opts)
    elif browser_name.lower() == "webkit":
        browser = p.webkit.launch(**launch_opts)
    else:
        # Preferir Chrome real instalado (fingerprint idêntico ao de um
        # usuário real, muito melhor contra anti-bot de sites gov.br).
        # Fallback silencioso para Chromium bundled se Chrome não existir.
        _use_chrome = os.getenv("USE_REAL_CHROME", "1").lower() in ("1", "true", "yes")
        if _use_chrome:
            try:
                browser = p.chromium.launch(channel="chrome", **launch_opts)
                _using_real_chrome = True
                logger.info("✅ Usando Chrome real instalado no sistema")
            except Exception:
                browser = p.chromium.launch(**launch_opts)
                logger.info("Chrome real não encontrado — usando Chromium bundled")
        else:
            browser = p.chromium.launch(**launch_opts)

    # --- Camada 2: context com perfil realista ---
    vp = random.choice(_REALISTIC_VIEWPORTS)

    # Se usando Chrome real, deixar o UA nativo (versão exata do browser
    # instalado). Se Chromium bundled, usar UA atualizado da lista.
    if _using_real_chrome:
        ua = None  # Chrome real já tem UA correto
    else:
        ua = random.choice(_REALISTIC_USER_AGENTS)

    ctx_opts: dict[str, Any] = {
        "viewport": vp,
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "color_scheme": "light",
        "ignore_https_errors": True,  # Alguns sites gov.br têm certificados problemáticos
        "extra_http_headers": {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    }
    if ua:
        ctx_opts["user_agent"] = ua

    context = browser.new_context(**ctx_opts)

    # --- Camada 3: playwright-stealth patches ---
    try:
        from playwright_stealth import Stealth  # type: ignore[import-untyped]
        stealth_kwargs: dict[str, Any] = {
            "navigator_webdriver": True,          # Remove navigator.webdriver
            "navigator_user_agent": True,         # Alinha UA no JS com o do context
            "navigator_languages": True,          # Idiomas consistentes
            "navigator_platform": True,           # Platform = Win32
            "navigator_plugins": True,            # Simula plugins reais
            "navigator_vendor": True,             # Google Inc.
            "chrome_runtime": True,               # window.chrome object
            "webgl_vendor": True,                 # WebGL renderer realista
            "navigator_languages_override": ("pt-BR", "pt"),
            "navigator_platform_override": "Win32",
        }
        # Só sobrescrever UA se estiver usando Chromium bundled
        if ua:
            stealth_kwargs["navigator_user_agent_override"] = ua

        stealth = Stealth(**stealth_kwargs)
        page = context.new_page()
        stealth.apply_stealth_sync(page)
        logger.info("🛡️ Stealth patches aplicados (navigator.webdriver mascarado)")
    except ImportError:
        logger.warning(
            "playwright-stealth não instalado — browser pode ser detectado como robô. "
            "Instale com: pip install playwright-stealth"
        )
        page = context.new_page()
    except Exception as exc:
        logger.warning(f"Erro ao aplicar stealth patches (continuando sem): {exc}")
        page = context.new_page()

    ua_display = ua[:60] if ua else "(Chrome nativo)"
    logger.info(f"🌐 Browser pronto — UA: {ua_display}… | Viewport: {vp['width']}×{vp['height']}")

    return p, browser, page


# ---------------------------------------------------------------------------
# API para BrowserPool — separa launch (browser) da criacao de contexto
# ---------------------------------------------------------------------------

def create_stealth_browser(
    browser_name: Optional[str] = None,
    headless: Optional[bool] = None,
) -> Tuple[Any, Any]:
    """Inicia Playwright e launcher do browser, SEM criar contexto/page.

    Usado pelo BrowserPool: 1 browser process + N contextos isolados.

    Returns:
        (playwright, browser) — sem context nem page.
    """
    browser_name = browser_name or os.getenv("DEFAULT_BROWSER", "chromium")

    if headless is None:
        env_headless = os.getenv("BROWSER_HEADLESS", "")
        if env_headless.lower() in ("1", "true", "yes"):
            headless = True
        elif env_headless.lower() in ("0", "false", "no"):
            headless = False
        else:
            headless = os.getenv("ENVIRONMENT", "development") == "production"

    logger.info(f"[Pool] Iniciando browser: {browser_name} (headless={headless})")

    p = sync_playwright().start()

    launch_opts: dict[str, Any] = {"headless": headless}
    if browser_name.lower() not in ("firefox", "webkit"):
        launch_opts["args"] = list(_STEALTH_CHROMIUM_ARGS)
        launch_opts["ignore_default_args"] = ["--enable-automation"]

    if browser_name.lower() == "firefox":
        browser = p.firefox.launch(**launch_opts)
    elif browser_name.lower() == "webkit":
        browser = p.webkit.launch(**launch_opts)
    else:
        _use_chrome = os.getenv("USE_REAL_CHROME", "1").lower() in ("1", "true", "yes")
        if _use_chrome:
            try:
                browser = p.chromium.launch(channel="chrome", **launch_opts)
                logger.info("[Pool] Usando Chrome real instalado")
            except Exception:
                browser = p.chromium.launch(**launch_opts)
                logger.info("[Pool] Chrome real nao encontrado — Chromium bundled")
        else:
            browser = p.chromium.launch(**launch_opts)

    return p, browser


def create_stealth_context(
    browser: Any,
    proxy: Optional[Any] = None,
) -> Tuple[Any, Any]:
    """Cria um BrowserContext isolado com stealth + perfil realista.

    Args:
        browser: Browser ja inicializado (de create_stealth_browser).
        proxy: URL string ou dict Playwright {server, username, password}.
               Se None, usa ProxyPool para round-robin (se PROXY_URLS setada).

    Returns:
        (context, page) — page ja criada e com stealth aplicado.
    """
    # --- Resolver proxy ---
    proxy_config: Optional[dict[str, str]] = None
    if proxy is not None:
        if isinstance(proxy, str):
            from browser.proxy import _to_playwright_proxy
            proxy_config = _to_playwright_proxy(proxy)
        elif isinstance(proxy, dict):
            proxy_config = proxy
    else:
        # Tentar pegar do pool de proxies (se configurado)
        try:
            from browser.proxy import ProxyPool
            proxy_config = ProxyPool.get_instance().next_playwright_config()
        except Exception:
            proxy_config = None

    # --- Perfil realista ---
    vp = random.choice(_REALISTIC_VIEWPORTS)
    ua = random.choice(_REALISTIC_USER_AGENTS)

    ctx_opts: dict[str, Any] = {
        "viewport": vp,
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "color_scheme": "light",
        "ignore_https_errors": True,
        "user_agent": ua,
        "extra_http_headers": {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    }
    if proxy_config:
        ctx_opts["proxy"] = proxy_config

    context = browser.new_context(**ctx_opts)

    # --- Stealth patches ---
    try:
        from playwright_stealth import Stealth  # type: ignore[import-untyped]
        stealth_kwargs: dict[str, Any] = {
            "navigator_webdriver": True,
            "navigator_user_agent": True,
            "navigator_languages": True,
            "navigator_platform": True,
            "navigator_plugins": True,
            "navigator_vendor": True,
            "chrome_runtime": True,
            "webgl_vendor": True,
            "navigator_languages_override": ("pt-BR", "pt"),
            "navigator_platform_override": "Win32",
            "navigator_user_agent_override": ua,
        }
        stealth = Stealth(**stealth_kwargs)
        page = context.new_page()
        stealth.apply_stealth_sync(page)
    except ImportError:
        logger.warning("[Pool] playwright-stealth nao instalado — sem stealth patches")
        page = context.new_page()
    except Exception as exc:
        logger.warning(f"[Pool] Erro stealth: {exc} — continuando sem")
        page = context.new_page()

    proxy_info = "sim" if proxy_config else "nao"
    logger.info(
        f"[Pool] Contexto criado | viewport={vp['width']}x{vp['height']} "
        f"proxy={proxy_info}"
    )

    return context, page


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
