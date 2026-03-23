"""
Business Logic Agent — Testa falhas de lógica de negócio
==========================================================
Cobre bypasses de plano freemium, rate limiting, escalação de
privilégios via API, e inconsistências de autorização por plano.

Alinhado ao OWASP A04:2021 — Insecure Design.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .base import Finding, SecurityAgent, Severity


class BusinessLogicAgent(SecurityAgent):
    """Testa regras de negócio e limites por plano."""

    name = "business_logic"
    category = "business_logic"

    def __init__(
        self,
        client: TestClient,
        free_user_headers: dict[str, str],
        paid_user_headers: dict[str, str] | None = None,
    ):
        self.client = client
        self.free_headers = free_user_headers
        self.paid_headers = paid_user_headers or free_user_headers

    def run(self) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._test_free_agent_access_gates())
        findings.extend(self._test_plan_spoofing_via_jwt())
        findings.extend(self._test_negative_amount_invoice())
        findings.extend(self._test_self_switch_plan())
        findings.extend(self._test_mass_assignment())
        return findings

    # ── Free user acessa agentes bloqueados ─────────────────────
    def _test_free_agent_access_gates(self) -> list[Finding]:
        """Free só pode usar contabilidade. Testa acesso aos outros."""
        findings: list[Finding] = []
        blocked_agents = ["clientes", "agenda", "assistente"]
        for agent in blocked_agents:
            resp = self.client.post(
                f"/api/agents/{agent}/execute",
                json={"action": "smart_chat", "message": "oi"},
                headers=self.free_headers,
            )
            if resp.status_code == 200:
                findings.append(Finding(
                    title=f"Bypass freemium: user free acessou agente '{agent}'",
                    description=f"Agente {agent} deveria ser bloqueado para plano free.",
                    severity=Severity.HIGH,
                    category="business_logic",
                    evidence={
                        "endpoint": f"POST /api/agents/{agent}/execute",
                        "user_plan": "free",
                        "status": resp.status_code,
                    },
                ))
        return findings

    # ── Plan spoofing via JWT ───────────────────────────────────
    def _test_plan_spoofing_via_jwt(self) -> list[Finding]:
        """Verifica que o plano vem do banco, não do token JWT."""
        findings: list[Finding] = []
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        # Cria token com plan=completo mas usando a chave de dev
        try:
            spoofed = pyjwt.encode(
                {
                    "user_id": 999999,
                    "email": "spoof@test.com",
                    "plan": "completo",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=24),
                    "iat": datetime.now(timezone.utc),
                },
                "dev-only-secret-change-in-production",
                algorithm="HS256",
            )
        except Exception:
            return findings

        resp = self.client.post(
            "/api/agents/agenda/execute",
            json={"action": "smart_chat", "message": "oi"},
            headers={"Authorization": f"Bearer {spoofed}"},
        )
        # Se o user_id=999999 não existe, esperamos 401/404.
        # Se retorna 200, o backend NÃO verificou o user no banco.
        if resp.status_code == 200:
            findings.append(Finding(
                title="Plan spoofing: backend confia no plan do JWT sem verificar banco",
                description="Token com plan=completo e user inexistente retornou 200.",
                severity=Severity.CRITICAL,
                category="business_logic",
                evidence={
                    "endpoint": "POST /api/agents/agenda/execute",
                    "spoofed_plan": "completo",
                    "spoofed_user_id": 999999,
                    "status": resp.status_code,
                },
            ))
        return findings

    # ── Fatura com valor negativo ───────────────────────────────
    def _test_negative_amount_invoice(self) -> list[Finding]:
        """Testa se é possível criar faturas com valor negativo ou zero."""
        findings: list[Finding] = []
        for amount in [-100.0, 0.0, -0.01]:
            resp = self.client.post("/api/crm/invoices", json={
                "client_id": 1,
                "amount": amount,
                "description": "Negative test",
                "due_date": "2026-12-31",
            }, headers=self.paid_headers)

            if resp.status_code in (200, 201):
                findings.append(Finding(
                    title=f"Fatura aceita com valor {amount}",
                    description="API permite criar faturas com valor não-positivo.",
                    severity=Severity.MEDIUM,
                    category="business_logic",
                    evidence={
                        "endpoint": "POST /api/crm/invoices",
                        "amount": amount,
                        "status": resp.status_code,
                    },
                ))
        return findings

    # ── Self-switch plan sem Stripe ─────────────────────────────
    def _test_self_switch_plan(self) -> list[Finding]:
        """Testa se user normal consegue trocar próprio plano via admin endpoint."""
        findings: list[Finding] = []
        resp = self.client.post(
            "/api/auth/admin/switch-plan",
            json={"email": "test@nexus.com", "new_plan": "completo"},
            headers=self.free_headers,
        )
        if resp.status_code == 200:
            findings.append(Finding(
                title="Self-switch plan: user trocou plano sem pagamento",
                description="Endpoint /admin/switch-plan acessível por user sem role admin.",
                severity=Severity.CRITICAL,
                category="business_logic",
                evidence={
                    "endpoint": "POST /api/auth/admin/switch-plan",
                    "status": resp.status_code,
                },
            ))
        return findings

    # ── Mass assignment ─────────────────────────────────────────
    def _test_mass_assignment(self) -> list[Finding]:
        """Testa se PUT /me aceita campos sensíveis (role, plan, status)."""
        findings: list[Finding] = []
        dangerous_fields = [
            {"role": "admin"},
            {"plan": "completo"},
            {"status": "active"},
            {"is_admin": True},
            {"requests_today": 0},
        ]
        for extra in dangerous_fields:
            resp = self.client.put(
                "/api/auth/me",
                json={"full_name": "Mass Assignment Test", **extra},
                headers=self.free_headers,
            )
            if resp.status_code == 200:
                # Verifica se o campo perigoso foi aceito
                me = self.client.get("/api/auth/me", headers=self.free_headers)
                if me.status_code == 200:
                    me_data = me.json()
                    key = list(extra.keys())[0]
                    if key in me_data and str(me_data[key]) == str(extra[key]):
                        findings.append(Finding(
                            title=f"Mass assignment: campo '{key}' aceito via PUT /me",
                            description=f"User conseguiu setar {key}={extra[key]} via PUT /me.",
                            severity=Severity.CRITICAL,
                            category="business_logic",
                            evidence={
                                "endpoint": "PUT /api/auth/me",
                                "field": key,
                                "value": extra[key],
                            },
                        ))
        return findings
