"""
test_auth_security.py — Autenticação e Autorização
=====================================================
Roda o AuthAgent para testar JWT forjado, tokens expirados,
algorithm confusion, endpoints sem auth, e mais.
"""

import pytest
from fastapi.testclient import TestClient

from tests.security.agents.auth_agent import AuthAgent


class TestAuthSecurity:
    """Testes de autenticação e controle de acesso."""

    def test_no_auth_bypass_vulnerabilities(
        self, client: TestClient, free_headers: dict, user_a: tuple
    ):
        """Nenhum bypass de autenticação deve funcionar."""
        _, user_id = user_a
        agent = AuthAgent(client, free_headers, user_id=user_id)
        findings = agent.run()

        critical = [f for f in findings if f.critical]
        assert not critical, (
            f"Encontradas {len(critical)} vulnerabilidades de auth:\n"
            + "\n".join(f"  - {f}" for f in critical)
        )

    def test_protected_endpoints_require_auth(self, client: TestClient):
        """Endpoints sensíveis devem retornar 401 sem Authorization.
        404 também é aceitável — indica que a rota não existe (sem bypass de auth).
        """
        endpoints = [
            "/api/auth/me",
            "/api/crm/clients",
            "/api/analytics/dashboard",
            "/api/agents/list",
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code in (401, 403, 404, 405, 307), (
                f"{ep} retornou {resp.status_code} sem auth (esperado 401/403/404)"
            )

    def test_forged_jwt_rejected(self, client: TestClient):
        """JWT assinado com chave errada deve ser rejeitado."""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        forged = pyjwt.encode(
            {
                "user_id": 1,
                "email": "hacker@evil.com",
                "plan": "completo",
                "exp": datetime.now(timezone.utc) + timedelta(hours=24),
                "iat": datetime.now(timezone.utc),
            },
            "CHAVE_ERRADA",
            algorithm="HS256",
        )
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {forged}"},
        )
        assert resp.status_code == 401, "JWT forjado não foi rejeitado"

    def test_no_password_hash_in_response(
        self, client: TestClient, free_headers: dict
    ):
        """Nenhum endpoint deve retornar password_hash."""
        for ep in ["/api/auth/me", "/api/auth/export-my-data"]:
            resp = client.get(ep, headers=free_headers)
            if resp.status_code == 200:
                assert "password_hash" not in resp.text, (
                    f"{ep} vaza password_hash na resposta"
                )
                assert "$2b$12$" not in resp.text, (
                    f"{ep} vaza hash bcrypt na resposta"
                )
