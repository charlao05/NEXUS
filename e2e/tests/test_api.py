"""
NEXUS E2E — Testes de Health e API
===================================
Verifica endpoints fundamentais via HTTP antes de testar o frontend.
"""

import requests
import pytest


class TestAPIHealth:
    """Testa os endpoints de saúde e metadados."""

    def test_backend_health(self, api_url):
        """Backend responde no /health."""
        r = requests.get(f"{api_url}/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "NEXUS" in data["service"]

    def test_backend_root(self, api_url):
        """Root retorna metadata."""
        r = requests.get(f"{api_url}/", timeout=10)
        assert r.status_code == 200

    def test_openapi_schema_segue_o_ambiente(self, api_url, backend_env):
        """OpenAPI: exposto fora de producao, FECHADO em producao.

        Este teste assertava 200 incondicionalmente e falhava no CI com 404.
        Nao era bug do backend: main.py:98-100 define
        `openapi_url=None if _is_prod else "/openapi.json"` — em producao o
        schema e desligado de proposito, e o docker-compose.yml sobe o backend
        com ENVIRONMENT=production (e o E2E deve testar o artefato que vai pro
        ar, nao uma configuracao de conveniencia).

        Entao o contrato depende do ambiente, e o teste pergunta ao proprio
        backend em qual ele esta rodando em vez de supor.
        """
        r = requests.get(f"{api_url}/openapi.json", timeout=10)

        if backend_env == "production":
            # Propriedade de SEGURANCA: em producao o schema nao vaza.
            assert r.status_code == 404, (
                "backend em producao esta expondo /openapi.json — main.py "
                "deveria passar openapi_url=None"
            )
            return

        assert r.status_code == 200
        data = r.json()
        assert "paths" in data
        # Deve ter ao menos as rotas básicas
        assert len(data["paths"]) >= 60

    def test_security_headers(self, api_url):
        """Headers de segurança presentes."""
        r = requests.get(f"{api_url}/health", timeout=10)
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"

    def test_cors_headers(self, api_url, base_url):
        """CORS permite a origem do frontend QUE ESTA NO AR.

        A origem era fixa em "http://localhost:5173" (porta do vite dev). No
        compose o frontend serve em http://frontend e o backend recebe
        CORS_ORIGINS=http://localhost,http://localhost:80,http://frontend,...
        — o preflight vinha de uma origem nao permitida e o Starlette respondia
        400 ("Disallowed CORS origin"). Falha legitima do teste, nao do app.

        Usar base_url amarra o teste ao frontend real de cada ambiente: e
        exatamente o par (frontend, backend) que precisa se conversar.
        """
        r = requests.options(
            f"{api_url}/health",
            headers={"Origin": base_url, "Access-Control-Request-Method": "GET"},
            timeout=10,
        )
        # CORS deve aceitar ou responder normalmente
        assert r.status_code in (200, 204, 405), (
            f"preflight de {base_url} recusado ({r.status_code}) — o backend nao "
            f"tem essa origem em CORS_ORIGINS"
        )


class TestAuthAPI:
    """Testa fluxo de autenticação via HTTP."""

    def test_signup_and_login(self, api_url, test_user):
        """Signup → Login → Token válido."""
        # Signup (pode falhar se user já existe)
        requests.post(
            f"{api_url}/api/auth/signup",
            json=test_user,
            timeout=10,
        )

        # Login
        r = requests.post(
            f"{api_url}/api/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        token = data["access_token"]

        # /me com token
        r2 = requests.get(
            f"{api_url}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert r2.status_code == 200
        me = r2.json()
        assert me["email"] == test_user["email"]

    def test_login_wrong_password(self, api_url, test_user):
        """Login com senha errada retorna 401."""
        r = requests.post(
            f"{api_url}/api/auth/login",
            json={"email": test_user["email"], "password": "WrongPassword!"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_protected_without_token(self, api_url):
        """Rotas protegidas retornam 401 sem token."""
        r = requests.get(f"{api_url}/api/auth/me", timeout=10)
        assert r.status_code == 401


class TestNotificationsAPI:
    """Testa endpoints de notificações via HTTP."""

    def test_unread_requires_auth(self, api_url):
        r = requests.get(f"{api_url}/api/notifications/unread", timeout=10)
        assert r.status_code == 401

    def test_unread_with_auth(self, api_url, test_user):
        # Login
        login_r = requests.post(
            f"{api_url}/api/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
            timeout=10,
        )
        if login_r.status_code != 200:
            pytest.skip("User not registered")
        token = login_r.json()["access_token"]

        r = requests.get(
            f"{api_url}/api/notifications/unread",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "notifications" in data
        assert "count" in data


class TestRateLimitAPI:
    """Testa rate limiting via HTTP."""

    def test_rate_limit_headers(self, api_url, backend_env):
        """Requests anônimos incluem headers de rate limit."""
        # Antes este teste batia em /openapi.json e so conferia status 200 —
        # nao verificava header nenhum, e nao PODERIA: /openapi.json esta em
        # RateLimitMiddleware.EXEMPT_PATHS, junto com /health e /. Rota isenta
        # nunca recebe X-RateLimit-*. Alem disso da 404 em producao, que foi a
        # falha visivel no CI.
        #
        # /api/notifications/unread e anonima (responde 401) e NAO e isenta:
        # passa pelo ramo que injeta os headers (rate_limit.py:342-344).
        r = requests.get(f"{api_url}/api/notifications/unread", timeout=10)
        assert r.status_code == 401

        # rate_limit.py:268-270 desliga o middleware inteiro quando
        # ENVIRONMENT==test. Exigir os headers ali seria cobrar um contrato que
        # o codigo declara nao ter — skip diz isso em voz alta, em vez de um
        # verde que nao significa nada. No compose (producao) o teste vale.
        if backend_env == "test":
            pytest.skip("rate limit desligado por decisao quando ENVIRONMENT=test")

        assert "X-RateLimit-Limit" in r.headers
        assert "X-RateLimit-Remaining" in r.headers
