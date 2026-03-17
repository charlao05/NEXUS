"""
test_full_sweep.py — Varredura completa (estilo Shannon)
==========================================================
Executa TODOS os agentes de segurança em paralelo e gera relatório.
Falha se qualquer vulnerabilidade CRITICAL for encontrada.

Este teste simula o comando único do Shannon: um único run que
cobre injection, auth, IDOR, XSS e business logic.
"""

import pytest
from fastapi.testclient import TestClient

from tests.security.agents.injection_agent import InjectionAgent
from tests.security.agents.auth_agent import AuthAgent
from tests.security.agents.xss_agent import XSSAgent
from tests.security.agents.business_logic_agent import BusinessLogicAgent
from tests.security.runner import run_all_agents, generate_report


class TestFullSecuritySweep:
    """Varredura completa de segurança — todos os agentes."""

    def test_full_security_sweep_no_critical(
        self,
        client: TestClient,
        user_a: tuple[dict[str, str], int],
        admin_headers: dict,
        free_headers: dict,
    ):
        """Executa todos os agentes e falha se houver CRITICAL."""
        headers_a, id_a = user_a

        agents = [
            InjectionAgent(client, admin_headers),
            AuthAgent(client, free_headers, admin_headers, user_id=id_a),
            XSSAgent(client, admin_headers),
            BusinessLogicAgent(client, free_headers, admin_headers),
        ]

        findings = run_all_agents(agents)

        # Gera relatório para auditoria
        report_path = generate_report(findings)
        print(f"\n📋 Relatório de segurança salvo em: {report_path}")

        # Resumo
        from tests.security.agents.base import Severity
        for sev in Severity:
            count = sum(1 for f in findings if f.severity == sev)
            if count:
                print(f"  {sev.value.upper()}: {count}")

        # Falha apenas em CRITICAL
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        assert not critical, (
            f"\n🚨 {len(critical)} vulnerabilidade(s) CRÍTICA(S) encontrada(s):\n"
            + "\n".join(f"  - {f.title}: {f.description}" for f in critical)
        )
