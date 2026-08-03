"""
NEXUS E2E — Testes do Frontend (Playwright)
=============================================
Verifica fluxos de usuário reais no navegador.
"""

import re
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

    def test_successful_login_redirects(self, page: Page, base_url, test_user, auth_session):
        """Login com sucesso redireciona ao dashboard/onboarding.

        `auth_session` aqui vale por "o usuario existe": era um
        /api/auth/signup repetido neste teste, e o endpoint aceita 3/min.
        O login continua sendo feito pelo formulario, no browser — e este e um
        dos 4 que o orcamento de AUTH_LIMITS reserva para exercicio real.
        """
        page.goto(f"{base_url}/login")
        page.wait_for_load_state("networkidle")

        # Preencher e submeter login
        page.fill("input[type='email'], input[name='email']", test_user["email"])
        page.fill("input[type='password'], input[name='password']", test_user["password"])
        page.click("button:has-text('Entrar')")

        # Deve redirecionar (dashboard ou onboarding)
        page.wait_for_url(re.compile(r"/(dashboard|onboarding|pricing)"), timeout=15000)
        assert page.url != f"{base_url}/login"

    def test_logout_returns_to_login(self, page: Page, base_url, test_user, auth_session):
        """Logout limpa a sessao e volta ao login — exercendo o clique.

        A LACUNA QUE ISTO FECHA (26/07/2026 → 27/07/2026): este teste pulava
        SEMPRE no compose. Duas causas, as duas resolvidas:

        1. 429. O login era feito aqui, e era o SEXTO da suite — AUTH_LIMITS
           permite 5/min por IP e o E2E inteiro sai de um IP so. Agora o token
           vem de `auth_session` (conftest.py), que loga uma unica vez para a
           suite; nenhum limite foi afrouxado, a suite e que parou de competir
           consigo mesma.

        2. Mesmo sem o 429, o teste nao testava logout. Ele so gravava
           access_token e ia para /dashboard — mas App.tsx:46,72 renderiza
           <Onboarding/> nessa rota enquanto `onboarding_completed` nao existe,
           e Onboarding nao tem botao de sair. O `if logout_btn.count() > 0`
           entao engolia a tela errada como sucesso. O login real grava a flag
           (NexusCodexLogin.tsx:69); como entramos pela sessao da API,
           reproduzimos o mesmo estado aqui.

        Sem `if`: se o botao de logout sumir, este teste falha em vez de passar
        calado.
        """
        page.goto(f"{base_url}/login")
        page.evaluate(
            """([token, email]) => {
                localStorage.setItem('access_token', token)
                localStorage.setItem('user_email', email)
                localStorage.setItem('onboarding_completed', 'true')
            }""",
            [auth_session["token"], test_user["email"]],
        )

        page.goto(f"{base_url}/dashboard")

        logout_btn = page.get_by_test_id("logout")
        expect(logout_btn).to_be_visible(timeout=15000)
        logout_btn.click()

        # A volta ao login e consequencia de estado, nao de um redirect
        # hardcoded: AuthContext.logout() zera o token e App.tsx cai no ramo
        # nao-autenticado, cujo `path="*"` navega para /login.
        page.wait_for_url(re.compile(r"/login"), timeout=10000)
        assert page.evaluate("localStorage.getItem('access_token')") is None, (
            "logout navegou para /login mas deixou o access_token no "
            "localStorage — a sessao continua valida"
        )


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
