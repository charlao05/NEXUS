"""
NEXUS — Playwright E2E Test Config
"""

import os
import pytest

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


@pytest.fixture
def test_user():
    """Credenciais do usuário de teste E2E."""
    return {
        "email": "e2e@nexus-test.com",
        "password": "E2eTestPassword123!",
        "full_name": "E2E Tester",
    }
