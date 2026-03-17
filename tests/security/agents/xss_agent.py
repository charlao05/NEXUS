"""
XSS Agent — Testa Cross-Site Scripting (reflected e stored)
=============================================================
Envia payloads XSS em campos de input e verifica se o output
reflete o script sem sanitização.

Alinhado ao OWASP A03:2021 — Injection (XSS).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .base import Finding, SecurityAgent, Severity


XSS_PAYLOADS = [
    '<script>alert("xss")</script>',
    '<img src=x onerror=alert(1)>',
    '"><svg onload=alert(1)>',
    "javascript:alert(1)",
    '<iframe src="javascript:alert(1)">',
    "{{constructor.constructor('return this')()}}", 
    "${7*7}",  # Template injection
    "{{7*7}}",
]


class XSSAgent(SecurityAgent):
    """Testa reflected e stored XSS nos endpoints da API."""

    name = "xss"
    category = "xss"

    def __init__(self, client: TestClient, auth_headers: dict[str, str]):
        self.client = client
        self.headers = auth_headers

    def run(self) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._test_signup_xss())
        findings.extend(self._test_client_xss())
        findings.extend(self._test_feedback_xss())
        findings.extend(self._test_security_headers())
        return findings

    # ── Signup full_name XSS ────────────────────────────────────
    def _test_signup_xss(self) -> list[Finding]:
        findings: list[Finding] = []
        for payload in XSS_PAYLOADS[:3]:
            resp = self.client.post("/api/auth/signup", json={
                "email": f"xss_{hash(payload) % 10000}@test.com",
                "password": "SafePass@123",
                "full_name": payload,
            })
            # Se o payload aparece não-escapado na resposta, é XSS reflected
            if resp.status_code in (200, 201) and payload in resp.text:
                findings.append(Finding(
                    title="XSS reflected no signup (full_name)",
                    description="Payload XSS refletido sem sanitização na resposta do signup.",
                    severity=Severity.MEDIUM,
                    category="xss",
                    evidence={
                        "endpoint": "POST /api/auth/signup",
                        "field": "full_name",
                        "payload": payload,
                        "reflected": True,
                    },
                ))
        return findings

    # ── Client name XSS (stored) ────────────────────────────────
    def _test_client_xss(self) -> list[Finding]:
        findings: list[Finding] = []
        for payload in XSS_PAYLOADS[:3]:
            # Cria cliente com XSS no nome
            create = self.client.post("/api/crm/clients", json={
                "name": payload,
                "email": "xss@test.com",
                "phone": "11900000000",
            }, headers=self.headers)

            if create.status_code not in (200, 201):
                continue

            data = create.json()
            cid = data.get("id") or data.get("client_id")
            if not cid:
                continue

            # Busca o cliente e verifica se o nome é retornado sem sanitização
            get = self.client.get(f"/api/crm/clients/{cid}", headers=self.headers)
            if get.status_code == 200 and payload in get.text:
                findings.append(Finding(
                    title="XSS stored em nome de cliente",
                    description="Payload XSS armazenado no nome do cliente e retornado sem escape.",
                    severity=Severity.MEDIUM,
                    category="xss",
                    evidence={
                        "endpoint": f"GET /api/crm/clients/{cid}",
                        "field": "name",
                        "payload": payload,
                        "stored": True,
                    },
                ))
        return findings

    # ── Feedback XSS ────────────────────────────────────────────
    def _test_feedback_xss(self) -> list[Finding]:
        findings: list[Finding] = []
        payload = '<script>alert("xss")</script>'
        resp = self.client.post("/api/auth/feedback", json={
            "message": payload,
            "rating": 5,
        }, headers=self.headers)

        if resp.status_code in (200, 201):
            # Verifica se o admin endpoint lista feedbacks com XSS
            admin_resp = self.client.get("/api/auth/feedbacks", headers=self.headers)
            if admin_resp.status_code == 200 and payload in admin_resp.text:
                findings.append(Finding(
                    title="XSS stored em feedback",
                    description="Payload XSS armazenado no feedback e exposto ao admin sem escape.",
                    severity=Severity.MEDIUM,
                    category="xss",
                    evidence={
                        "endpoint": "GET /api/auth/feedbacks",
                        "payload": payload,
                    },
                ))
        return findings

    # ── Security headers ────────────────────────────────────────
    def _test_security_headers(self) -> list[Finding]:
        """Verifica se headers de segurança anti-XSS estão presentes."""
        findings: list[Finding] = []
        resp = self.client.get("/health")

        headers_lower = {k.lower(): v for k, v in resp.headers.items()}

        required_headers = {
            "x-content-type-options": "nosniff",
            "x-frame-options": None,  # DENY ou SAMEORIGIN
        }

        for header, expected_value in required_headers.items():
            value = headers_lower.get(header)
            if not value:
                findings.append(Finding(
                    title=f"Header de segurança ausente: {header}",
                    description=f"Header {header} não está presente — aumenta risco de XSS/clickjacking.",
                    severity=Severity.LOW,
                    category="xss",
                    evidence={"header": header, "present": False},
                ))
            elif expected_value and value.lower() != expected_value.lower():
                findings.append(Finding(
                    title=f"Header {header} com valor inesperado",
                    description=f"Esperado '{expected_value}', recebido '{value}'.",
                    severity=Severity.INFO,
                    category="xss",
                    evidence={"header": header, "expected": expected_value, "actual": value},
                ))
        return findings
