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

    def test_free_user_blocked_from_paid_agents(
        self, client: TestClient, free_headers: dict
    ):
        """User free NÃO pode executar agentes pagos."""
        blocked = ["clientes", "cobranca", "agenda", "assistente"]
        for agent in blocked:
            resp = client.post(
                f"/api/agents/{agent}/execute",
                json={"action": "smart_chat", "message": "teste"},
                headers=free_headers,
            )
            assert resp.status_code in (403, 429), (
                f"Free user acessou agente '{agent}' (status={resp.status_code})"
            )
