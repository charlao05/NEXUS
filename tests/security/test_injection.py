"""
test_injection.py — SQL Injection, NoSQL Injection, Command Injection
======================================================================
Roda o InjectionAgent contra todos os endpoints da API NEXUS.
Falha se encontrar qualquer vulnerabilidade HIGH ou CRITICAL.
"""

import pytest
from fastapi.testclient import TestClient

from tests.security.agents.injection_agent import InjectionAgent


class TestInjection:
    """Testes de injeção contra a API."""

    def test_no_sql_injection_vulnerabilities(self, client: TestClient, admin_headers: dict):
        """Nenhum endpoint deve vazar erros SQL com payloads de injeção."""
        agent = InjectionAgent(client, admin_headers)
        findings = agent.run()

        critical = [f for f in findings if f.critical]
        assert not critical, (
            f"Encontradas {len(critical)} vulnerabilidades de injeção:\n"
            + "\n".join(f"  - {f}" for f in critical)
        )

    def test_login_rejects_sqli_gracefully(self, client: TestClient):
        """Login com payloads SQL deve retornar 401/422, nunca 500."""
        payloads = ["' OR '1'='1", "'; DROP TABLE users; --"]
        for p in payloads:
            resp = client.post("/api/auth/login", json={
                "email": f"{p}@test.com",
                "password": p,
            })
            assert resp.status_code != 500, (
                f"Login retornou 500 com payload: {p}"
            )
