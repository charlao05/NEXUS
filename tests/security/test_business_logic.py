"""
test_business_logic.py — Testes de lógica de negócio
======================================================
Bypass de planos, faturas negativas, mass assignment, etc.
"""

import pytest
from fastapi.testclient import TestClient

from tests.security.agents.business_logic_agent import BusinessLogicAgent


class TestBusinessLogic:
    """Testes de regras de negócio e segurança lógica."""

    def test_no_business_logic_bypass(
        self, client: TestClient, free_headers: dict, admin_headers: dict
    ):
        """Nenhum bypass de lógica de negócio deve funcionar."""
        agent = BusinessLogicAgent(client, free_headers, admin_headers)
        findings = agent.run()

        critical = [f for f in findings if f.critical]
        assert not critical, (
            f"Encontrados {len(critical)} bypasses de lógica:\n"
            + "\n".join(f"  - {f}" for f in critical)
        )

    def test_free_user_rate_limited(
        self, client: TestClient, free_headers: dict
    ):
        """User free tem acesso a todos os agentes (degustação); o bloqueio
        ocorre por rate limit (429) ao esgotar o limite diário, não por plano (403)."""
        agents_degustacao = ["clientes", "agenda"]
        for agent in agents_degustacao:
            resp = client.post(
                f"/api/agents/{agent}/execute",
                json={"action": "smart_chat", "message": "teste"},
                headers=free_headers,
            )
            assert resp.status_code != 403, (
                f"Free user bloqueado por plano no agente '{agent}' — "
                f"deveria ser permitido (200) ou limitado por rate (429), "
                f"não bloqueado por plano (status={resp.status_code})"
            )
