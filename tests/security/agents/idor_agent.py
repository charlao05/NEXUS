"""
IDOR Agent — Testa Insecure Direct Object Reference
=====================================================
Verifica se um usuário autenticado pode acessar/modificar/deletar
recursos de OUTRO usuário apenas manipulando IDs nas URLs.

Alinhado ao OWASP A01:2021 — Broken Access Control.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .base import Finding, SecurityAgent, Severity


class IDORAgent(SecurityAgent):
    """Testa acesso cruzado entre usuários (IDOR)."""

    name = "idor"
    category = "idor"

    def __init__(
        self,
        client: TestClient,
        user_a_headers: dict[str, str],
        user_b_headers: dict[str, str],
        user_a_id: int,
        user_b_id: int,
    ):
        self.client = client
        self.headers_a = user_a_headers
        self.headers_b = user_b_headers
        self.user_a_id = user_a_id
        self.user_b_id = user_b_id

    def run(self) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._test_client_idor())
        findings.extend(self._test_chat_history_idor())
        findings.extend(self._test_invoice_idor())
        findings.extend(self._test_export_data_idor())
        return findings

    # ── CRM Client IDOR ────────────────────────────────────────
    def _test_client_idor(self) -> list[Finding]:
        """User A cria cliente → User B tenta acessar."""
        findings: list[Finding] = []

        # User A cria cliente
        create_resp = self.client.post("/api/crm/clients", json={
            "name": "Cliente IDOR Test",
            "email": "idor@test.com",
            "phone": "11999990000",
        }, headers=self.headers_a)

        if create_resp.status_code not in (200, 201):
            return findings  # Não conseguiu criar — pula

        client_data = create_resp.json()
        client_id = client_data.get("id") or client_data.get("client_id")
        if not client_id:
            return findings

        # User B tenta acessar
        resp = self.client.get(
            f"/api/crm/clients/{client_id}",
            headers=self.headers_b,
        )
        if resp.status_code == 200:
            resp_data = resp.json()
            # Verifica se realmente retornou dados do cliente de outro user
            if resp_data.get("name") == "Cliente IDOR Test":
                findings.append(Finding(
                    title="IDOR: Acesso ao cliente de outro usuário",
                    description=f"User B acessou cliente {client_id} criado por User A.",
                    severity=Severity.HIGH,
                    category="idor",
                    evidence={
                        "endpoint": f"GET /api/crm/clients/{client_id}",
                        "owner": self.user_a_id,
                        "accessor": self.user_b_id,
                        "status": resp.status_code,
                    },
                ))

        # User B tenta deletar
        del_resp = self.client.delete(
            f"/api/crm/clients/{client_id}",
            headers=self.headers_b,
        )
        if del_resp.status_code in (200, 204):
            findings.append(Finding(
                title="IDOR: Deleção de cliente de outro usuário",
                description=f"User B deletou cliente {client_id} de User A.",
                severity=Severity.CRITICAL,
                category="idor",
                evidence={
                    "endpoint": f"DELETE /api/crm/clients/{client_id}",
                    "status": del_resp.status_code,
                },
            ))

        return findings

    # ── Chat history IDOR ──────────────────────────────────────
    def _test_chat_history_idor(self) -> list[Finding]:
        """Verifica se User B pode ler histórico de chat de User A."""
        findings: list[Finding] = []
        agents = ["contabilidade", "clientes", "agenda"]
        for agent in agents:
            resp = self.client.get(
                f"/api/chat/history/{agent}",
                headers=self.headers_b,
            )
            if resp.status_code == 200:
                data = resp.json()
                messages = data if isinstance(data, list) else data.get("messages", [])
                # Se retornou mensagens que pertencem ao User A
                for msg in messages:
                    msg_user = msg.get("user_id")
                    if msg_user and int(msg_user) == self.user_a_id:
                        findings.append(Finding(
                            title=f"IDOR: Chat history do {agent} vazou para outro user",
                            description=f"User B leu mensagens de User A no agente {agent}.",
                            severity=Severity.HIGH,
                            category="idor",
                            evidence={
                                "endpoint": f"GET /api/chat/history/{agent}",
                                "leaked_user_id": self.user_a_id,
                            },
                        ))
                        break
        return findings

    # ── Invoice IDOR ──────────────────────────────────────────
    def _test_invoice_idor(self) -> list[Finding]:
        """User A cria fatura → User B tenta acessar."""
        findings: list[Finding] = []

        create_resp = self.client.post("/api/crm/invoices", json={
            "client_id": 999999,  # ID fictício
            "amount": 100.0,
            "description": "IDOR test invoice",
            "due_date": "2026-12-31",
        }, headers=self.headers_a)

        if create_resp.status_code in (200, 201):
            inv_data = create_resp.json()
            inv_id = inv_data.get("id") or inv_data.get("invoice_id")
            if inv_id:
                resp = self.client.get(
                    f"/api/crm/invoices/{inv_id}",
                    headers=self.headers_b,
                )
                if resp.status_code == 200:
                    findings.append(Finding(
                        title="IDOR: Acesso à fatura de outro usuário",
                        description=f"User B acessou fatura {inv_id} de User A.",
                        severity=Severity.HIGH,
                        category="idor",
                        evidence={
                            "endpoint": f"GET /api/crm/invoices/{inv_id}",
                            "status": resp.status_code,
                        },
                    ))
        return findings

    # ── Export data IDOR ──────────────────────────────────────
    def _test_export_data_idor(self) -> list[Finding]:
        """Verifica que /export-my-data só retorna dados do user autenticado."""
        findings: list[Finding] = []
        resp = self.client.get(
            "/api/auth/export-my-data",
            headers=self.headers_b,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Se retornou dados com user_id de User A, é IDOR
            exported_id = data.get("user_id") or data.get("id")
            if exported_id and int(exported_id) == self.user_a_id:
                findings.append(Finding(
                    title="IDOR: Export-my-data retornou dados de outro user",
                    description="Endpoint de export retornou dados do User A quando autenticado como User B.",
                    severity=Severity.CRITICAL,
                    category="idor",
                    evidence={
                        "endpoint": "GET /api/auth/export-my-data",
                        "expected_user": self.user_b_id,
                        "returned_user": exported_id,
                    },
                ))
        return findings
