"""
test_xss.py — Cross-Site Scripting (reflected e stored)
========================================================
Verifica que payloads XSS não são refletidos/armazenados sem sanitização.
"""

import pytest
from fastapi.testclient import TestClient

from tests.security.agents.xss_agent import XSSAgent


class TestXSS:
    """Testes anti-XSS."""

    def test_no_xss_vulnerabilities(self, client: TestClient, admin_headers: dict):
        """Nenhum payload XSS deve ser refletido sem escape."""
        agent = XSSAgent(client, admin_headers)
        findings = agent.run()

        critical = [f for f in findings if f.critical]
        high = [f for f in findings if f.severity.value == "high"]
        assert not critical and not high, (
            f"Encontradas vulnerabilidades XSS:\n"
            + "\n".join(f"  - {f}" for f in critical + high)
        )

    def test_security_headers_present(self, client: TestClient):
        """Headers de proteção anti-XSS/clickjacking devem estar presentes."""
        resp = client.get("/health")
        headers_lower = {k.lower(): v for k, v in resp.headers.items()}
        assert "x-content-type-options" in headers_lower, "Header x-content-type-options ausente"
