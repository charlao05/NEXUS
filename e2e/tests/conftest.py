"""
NEXUS — Playwright E2E Test Config
"""

import os
import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:5173")
API_URL = os.getenv("API_URL", "http://localhost:8000")


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


@pytest.fixture
def test_user():
    """Credenciais do usuário de teste E2E."""
    return {
        "email": "e2e@nexus-test.com",
        "password": "E2eTestPassword123!",
        "full_name": "E2E Tester",
    }
