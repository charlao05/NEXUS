"""
test_idor.py — Insecure Direct Object Reference
==================================================
Verifica isolamento de dados entre usuários:
User A não pode acessar recursos de User B.
"""

import pytest
from fastapi.testclient import TestClient

from tests.security.agents.idor_agent import IDORAgent


class TestIDOR:
    """Testes de isolamento de dados entre usuários."""

    def test_no_cross_user_access(
        self,
        client: TestClient,
        user_a: tuple[dict[str, str], int],
        user_b: tuple[dict[str, str], int],
    ):
        """Nenhum usuário deve acessar recursos de outro."""
        headers_a, id_a = user_a
        headers_b, id_b = user_b
        agent = IDORAgent(client, headers_a, headers_b, id_a, id_b)
        findings = agent.run()

        critical = [f for f in findings if f.critical]
        assert not critical, (
            f"Encontradas {len(critical)} vulnerabilidades IDOR:\n"
            + "\n".join(f"  - {f}" for f in critical)
        )
