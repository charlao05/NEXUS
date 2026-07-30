"""
NEXUS — Playwright E2E Test Config
"""

import os
import time

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:5173")
API_URL = os.getenv("API_URL", "http://localhost:8000")

# Teto de espera quando um login leva 429. O Retry-After do limite POR MINUTO e
# 60s; o do limite POR HORA e 3600s, e nesse caso esperar nao e uma opcao — vale
# mais falhar dizendo o porque. Ver `auth_session`.
_LOGIN_RETRY_MAX_WAIT = 65


@pytest.fixture(scope="session")
def browser_context_args():
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def api_url():
    return API_URL


@pytest.fixture(scope="session")
def backend_env(api_url):
    """Ambiente em que o backend REALMENTE esta rodando, perguntado a ele.

    Nao da para deduzir do lado de fora: o docker-compose.yml define
    `ENVIRONMENT: "production"` no bloco `environment:`, que tem precedencia
    sobre o `env_file: .env` — entao o ENVIRONMENT=test do .env gerado no CI e
    ignorado pelo container. Supor o ambiente errado ja custou tres testes
    vermelhos (openapi, cors, rate limit).

    Parte do comportamento do backend depende disso POR DECISAO:
      - /openapi.json e desligado em producao        (main.py:98-100)
      - rate limiting e desligado quando =="test"    (rate_limit.py:268-270)
    """
    try:
        r = requests.get(f"{api_url}/health", timeout=10)
        return (r.json().get("config", {}).get("environment") or "").lower()
    except Exception:  # noqa: BLE001
        return "unknown"


@pytest.fixture(scope="session")
def test_user():
    """Credenciais do usuário de teste E2E."""
    return {
        "email": "e2e@nexus-test.com",
        "password": "E2eTestPassword123!",
        "full_name": "E2E Tester",
    }


@pytest.fixture(scope="session")
def auth_session(api_url, test_user):
    """Sessao autenticada compartilhada — UM login para a suite inteira.

    POR QUE ISTO EXISTE
    -------------------
    /api/auth/login aceita 5 tentativas por minuto por IP (AUTH_LIMITS,
    backend/app/api/rate_limit.py:81-86). Todo o E2E sai de um unico container
    e chega ao backend com UM unico IP: os testes de API batem direto em
    http://backend:8000, e os de browser passam pelo nginx do frontend, que
    repassa o IP de origem em X-Forwarded-For (nginx.conf:32) — que e
    exatamente o que _get_client_ip le. Ou seja: a suite inteira divide um
    orcamento de 5 logins por minuto.

    A suite gastava 6, porque dois testes faziam um login so para conseguir um
    token. O sexto levava 429 e test_logout_returns_to_login caia no
    pytest.skip SEMPRE — run 30230154081: "18 passed, 1 skipped". O fluxo de
    logout nunca foi exercido no CI.

    O limite esta certo e NAO foi afrouxado: brute force em /api/auth/login e
    exatamente o que ele existe para barrar. O que mudou foi a suite parar de
    competir consigo mesma — quem so precisa de "um token valido" reusa este
    fixture. Sobram 4 chamadas, todas as que exercem o login de verdade:

      1. este fixture                          — o login que da certo
      2. test_login_wrong_password             — o 401
      3. test_login_with_invalid_credentials   — o formulario, no browser
      4. test_successful_login_redirects       — o fluxo completo, no browser

    Tambem centraliza o signup: antes dois testes cadastravam o mesmo usuario
    (/api/auth/signup e limitado a 3/min).
    """
    # Signup e idempotente do ponto de vista da suite: se o usuario ja existe o
    # backend recusa e seguimos para o login normalmente.
    requests.post(f"{api_url}/api/auth/signup", json=test_user, timeout=10)

    credentials = {"email": test_user["email"], "password": test_user["password"]}
    r = requests.post(f"{api_url}/api/auth/login", json=credentials, timeout=10)

    # Rede de seguranca. Se alguem adicionar um teste que volte a estourar o
    # orcamento, esperamos a janela e tentamos de novo em vez de pular: um skip
    # aqui derrubaria a suite inteira de volta ao verde que nao testa nada.
    if r.status_code == 429:
        wait = min(int(r.headers.get("Retry-After", 60)), _LOGIN_RETRY_MAX_WAIT)
        time.sleep(wait + 1)
        r = requests.post(f"{api_url}/api/auth/login", json=credentials, timeout=10)

    assert r.status_code == 200, (
        f"login da sessao E2E falhou (HTTP {r.status_code}): {r.text[:300]}\n"
        "Se for 429 mesmo depois da espera, o estourado e o limite POR HORA "
        "(30/h): o contador vive no Redis, que tem volume persistente, entao "
        "ele soma execucoes anteriores do compose. `docker compose down -v` zera."
    )

    data = r.json()
    return {"response": r, "data": data, "token": data["access_token"]}
