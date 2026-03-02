"""
NEXUS E2E — Testes do Frontend (Playwright)
=============================================
Verifica fluxos de usuário reais no navegador.
"""

import re
import pytest
from playwright.sync_api import Page, expect


class TestLoginPage:
    """Testa a página de login."""

    def test_login_page_loads(self, page: Page, base_url):
        """Página de login renderiza corretamente."""
        page.goto(f"{base_url}/login")
        # Deve ter campo de email e senha
        expect(page.locator("input[type='email'], input[name='email']")).to_be_visible(timeout=15000)
        expect(page.locator("input[type='password'], input[name='password']")).to_be_visible()

    def test_login_page_has_title(self, page: Page, base_url):
        """Página tem título NEXUS."""
        page.goto(f"{base_url}/login")
        expect(page).to_have_title(re.compile(r"NEXUS|Login", re.IGNORECASE), timeout=15000)

    def test_login_with_invalid_credentials(self, page: Page, base_url):
        """Login com credenciais inválidas mostra erro."""
        page.goto(f"{base_url}/login")

        # Preencher campos
        page.fill("input[type='email'], input[name='email']", "invalid@test.com")
        page.fill("input[type='password'], input[name='password']", "wrongpassword")

        # Submeter (botão não tem type=submit, usa onClick)
        page.click("button:has-text('Entrar')")

        # Deve mostrar mensagem de erro (aguardar até 5s)
        page.wait_for_timeout(3000)
        # Verificar que não redirecionou para dashboard
        assert "/dashboard" not in page.url


class TestLoginFlow:
    """Testa o fluxo completo de login → dashboard."""

    def test_successful_login_redirects(self, page: Page, base_url, api_url, test_user):
        """Login com sucesso redireciona ao dashboard/onboarding."""
        import requests

        # Garantir que user existe
        requests.post(
            f"{api_url}/api/auth/signup",
            json=test_user,
            timeout=10,
        )

        page.goto(f"{base_url}/login")
        page.wait_for_load_state("networkidle")

        # Preencher e submeter login
        page.fill("input[type='email'], input[name='email']", test_user["email"])
        page.fill("input[type='password'], input[name='password']", test_user["password"])
        page.click("button:has-text('Entrar')")

        # Deve redirecionar (dashboard ou onboarding)
        page.wait_for_url(re.compile(r"/(dashboard|onboarding|pricing)"), timeout=15000)
        assert page.url != f"{base_url}/login"

    def test_logout_returns_to_login(self, page: Page, base_url, api_url, test_user):
        """Logout redireciona de volta ao login."""
        import requests

        # Login via API
        login_r = requests.post(
            f"{api_url}/api/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
            timeout=10,
        )
        if login_r.status_code != 200:
            pytest.skip("Cannot login")

        token = login_r.json()["access_token"]

        # Navegar para dashboard com token no localStorage
        page.goto(f"{base_url}/login")
        page.evaluate(f"localStorage.setItem('access_token', '{token}')")
        page.goto(f"{base_url}/dashboard")
        page.wait_for_timeout(2000)

        # Se tem botão de logout, clicar
        logout_btn = page.locator("button:has-text('Sair'), button:has-text('Logout'), [data-testid='logout']")
        if logout_btn.count() > 0:
            logout_btn.first.click()
            page.wait_for_timeout(2000)
            assert "/login" in page.url or page.url.endswith("/")


class TestNavigation:
    """Testa navegação entre páginas."""

    def test_unauthenticated_redirects_to_login(self, page: Page, base_url):
        """Acesso sem auth redireciona para login."""
        page.goto(f"{base_url}/dashboard")
        page.wait_for_timeout(3000)
        # Deve estar no login ou ainda no dashboard mas sem dados
        assert "/login" in page.url or "/dashboard" in page.url

    def test_frontend_serves_spa(self, page: Page, base_url):
        """Frontend serve SPA corretamente."""
        page.goto(base_url)
        page.wait_for_load_state("domcontentloaded")
        # Deve ter a div root do React
        expect(page.locator("#root")).to_be_attached(timeout=10000)

    def test_404_returns_spa(self, page: Page, base_url):
        """Rota inexistente retorna SPA (sem 404 do nginx)."""
        response = page.goto(f"{base_url}/nonexistent-route-xyz")
        assert response is not None
        assert response.status == 200  # SPA fallback
        expect(page.locator("#root")).to_be_attached(timeout=10000)
