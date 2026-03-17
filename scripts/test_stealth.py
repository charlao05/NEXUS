"""
Testa que o browser com stealth NAO e detectado como robo.
Valida todas as camadas de anti-deteccao sem acessar sites externos.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} {detail}")


def test_stealth_constants():
    print("\n--- Constants ---")
    from backend.browser.playwright_client import (
        _STEALTH_CHROMIUM_ARGS,
        _REALISTIC_USER_AGENTS,
        _REALISTIC_VIEWPORTS,
    )
    check("Has chromium stealth args", len(_STEALTH_CHROMIUM_ARGS) >= 5)
    check(
        "disable-blink-features in args",
        any("AutomationControlled" in a for a in _STEALTH_CHROMIUM_ARGS),
    )
    check("Has realistic user agents", len(_REALISTIC_USER_AGENTS) >= 3)
    check("No HeadlessChrome in any UA", not any("HeadlessChrome" in ua for ua in _REALISTIC_USER_AGENTS))
    check("Has realistic viewports", len(_REALISTIC_VIEWPORTS) >= 3)
    check("All viewports have width/height", all("width" in v and "height" in v for v in _REALISTIC_VIEWPORTS))


def test_stealth_library():
    print("\n--- Stealth Library ---")
    try:
        from playwright_stealth import Stealth
        check("playwright-stealth importable", True)
        s = Stealth(navigator_webdriver=True)
        check("Stealth instance created", hasattr(s, "apply_stealth_sync"))
    except ImportError:
        check("playwright-stealth importable", False, "pip install playwright-stealth")


def test_browser_launch_headed():
    """Test com browser headed (como em dev para sites gov.br)."""
    print("\n--- Browser Launch (headed) ---")
    from backend.browser.playwright_client import iniciar_navegador, fechar_navegador

    pw, browser, page = iniciar_navegador(headless=False)
    try:
        # navigator.webdriver must be False
        wd = page.evaluate("() => navigator.webdriver")
        check("navigator.webdriver = false", wd is False or wd is None, f"got {wd}")

        # User-Agent must not contain HeadlessChrome
        ua = page.evaluate("() => navigator.userAgent")
        check("UA no HeadlessChrome", "HeadlessChrome" not in ua, ua[:60])
        check("UA contains Chrome/", "Chrome/" in ua)

        # Languages must include pt-BR
        langs = page.evaluate("() => navigator.languages")
        check("Languages includes pt-BR", "pt-BR" in langs, f"got {langs}")

        # window.chrome must exist (headed)
        has_chrome = page.evaluate("() => !!window.chrome")
        check("window.chrome exists (headed)", has_chrome is True)

        # plugins > 0 (headed)
        plugins = page.evaluate("() => navigator.plugins.length")
        check("navigator.plugins.length > 0 (headed)", plugins > 0, f"got {plugins}")

        # Viewport must be set to a realistic resolution
        vp = page.viewport_size
        check("Viewport set", vp is not None and vp.get("width", 0) >= 1280)

        # navigator.platform should be Win32
        platform = page.evaluate("() => navigator.platform")
        check("Platform is Win32", platform == "Win32", f"got {platform}")

    finally:
        fechar_navegador(pw, browser)


def test_browser_launch_headless():
    """Test com browser headless (como em producao)."""
    print("\n--- Browser Launch (headless) ---")
    from backend.browser.playwright_client import iniciar_navegador, fechar_navegador

    pw, browser, page = iniciar_navegador(headless=True)
    try:
        wd = page.evaluate("() => navigator.webdriver")
        check("navigator.webdriver = false (headless)", wd is False or wd is None, f"got {wd}")

        ua = page.evaluate("() => navigator.userAgent")
        check("UA no HeadlessChrome (headless)", "HeadlessChrome" not in ua, ua[:60])

        langs = page.evaluate("() => navigator.languages")
        check("Languages pt-BR (headless)", "pt-BR" in langs)

    finally:
        fechar_navegador(pw, browser)


def test_tools_bridge():
    """Test que o tools/browser.py usa o iniciar_navegador corretamente."""
    print("\n--- Tools Bridge ---")
    from backend.orchestrator.tools.browser import _ensure_browser, shutdown_browser, _browser_state

    # Reset state
    _browser_state["playwright"] = None
    _browser_state["browser"] = None
    _browser_state["page"] = None

    try:
        page = _ensure_browser()
        check("_ensure_browser returns page", page is not None)

        wd = page.evaluate("() => navigator.webdriver")
        check("Stealth via tools bridge", wd is False or wd is None, f"got {wd}")

    finally:
        shutdown_browser()
        check("shutdown_browser OK", _browser_state["page"] is None)


if __name__ == "__main__":
    print("=" * 50)
    print("NEXUS Stealth Browser Tests")
    print("=" * 50)

    test_stealth_constants()
    test_stealth_library()
    test_browser_launch_headed()
    test_browser_launch_headless()
    test_tools_bridge()

    print("\n" + "=" * 50)
    total = passed + failed
    print(f"Results: {passed} passed, {failed} failed, {total} total")
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"SOME TESTS FAILED ({failed})")
    sys.exit(1 if failed else 0)
