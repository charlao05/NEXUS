"""
Injection Agent — Testa SQL Injection, NoSQL Injection e Command Injection
===========================================================================
Envia payloads de injeção em todos os parâmetros de input (query params,
JSON body, path params) e verifica se a resposta vaza erros de banco,
executa comandos ou retorna dados inesperados.

Alinhado ao OWASP A03:2021 — Injection.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .base import Finding, SecurityAgent, Severity


# ── Payloads de teste (não destrutivos — apenas detecção) ──────────────
SQLI_PAYLOADS = [
    "' OR '1'='1",
    "' OR '1'='1' --",
    "'; SELECT 1; --",
    "1 UNION SELECT NULL--",
    "' AND 1=CONVERT(int,(SELECT @@version))--",
    "'; WAITFOR DELAY '0:0:3'--",
    "admin'--",
]

NOSQL_PAYLOADS = [
    '{"$gt": ""}',
    '{"$ne": null}',
    '{"$regex": ".*"}',
]

COMMAND_INJECTION_PAYLOADS = [
    "; ls",
    "| cat /etc/passwd",
    "$(whoami)",
    "`id`",
]

# Padrões que indicam vazamento de erro de banco
_SQL_ERROR_SIGNATURES = [
    "syntax error",
    "sqlite3.operationalerror",
    "operationalerror",
    "sqlalchemy.exc",
    "psycopg2",
    "pg_catalog",
    "mysql",
    "ora-",
    "unterminated",
    "unrecognized token",
    "near \"",
    "stacktrace",
    "traceback",
    "internal server error",  # 500 genérico pode indicar injeção que crashou
]


class InjectionAgent(SecurityAgent):
    """Testa endpoints contra SQL/NoSQL/Command injection."""

    name = "injection"
    category = "injection"

    def __init__(self, client: TestClient, auth_headers: dict[str, str]):
        self.client = client
        self.headers = auth_headers

    def run(self) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._test_login_injection())
        findings.extend(self._test_signup_injection())
        findings.extend(self._test_search_injection())
        findings.extend(self._test_crm_injection())
        findings.extend(self._test_agent_chat_injection())
        return findings

    # ── Login ───────────────────────────────────────────────────
    def _test_login_injection(self) -> list[Finding]:
        findings: list[Finding] = []
        for payload in SQLI_PAYLOADS:
            resp = self.client.post("/api/auth/login", json={
                "email": f"{payload}@test.com",
                "password": payload,
            })
            if self._has_sql_leak(resp.text, resp.status_code):
                findings.append(Finding(
                    title=f"SQL Injection no login (payload: {payload[:30]})",
                    description="Endpoint de login vaza erro SQL ao receber payload malicioso.",
                    severity=Severity.CRITICAL,
                    category="injection",
                    evidence={
                        "endpoint": "POST /api/auth/login",
                        "payload": payload,
                        "status": resp.status_code,
                        "response_snippet": resp.text[:200],
                    },
                ))
        return findings

    # ── Signup ──────────────────────────────────────────────────
    def _test_signup_injection(self) -> list[Finding]:
        findings: list[Finding] = []
        for payload in SQLI_PAYLOADS[:3]:
            resp = self.client.post("/api/auth/signup", json={
                "email": "injection_test@nexus.com",
                "password": "SafePass@123",
                "full_name": payload,
            })
            if self._has_sql_leak(resp.text, resp.status_code):
                findings.append(Finding(
                    title=f"SQL Injection no signup (campo full_name)",
                    description="Campo full_name do signup é vulnerável a injeção SQL.",
                    severity=Severity.CRITICAL,
                    category="injection",
                    evidence={
                        "endpoint": "POST /api/auth/signup",
                        "field": "full_name",
                        "payload": payload,
                        "status": resp.status_code,
                        "response_snippet": resp.text[:200],
                    },
                ))
        return findings

    # ── CRM search/create ─────────────────────────────────────
    def _test_search_injection(self) -> list[Finding]:
        findings: list[Finding] = []
        for payload in SQLI_PAYLOADS:
            resp = self.client.get(
                "/api/crm/clients",
                params={"search": payload},
                headers=self.headers,
            )
            if self._has_sql_leak(resp.text, resp.status_code):
                findings.append(Finding(
                    title="SQL Injection na busca de clientes",
                    description="Parâmetro search de /api/crm/clients vaza erro SQL.",
                    severity=Severity.HIGH,
                    category="injection",
                    evidence={
                        "endpoint": "GET /api/crm/clients",
                        "param": "search",
                        "payload": payload,
                        "status": resp.status_code,
                    },
                ))
        return findings

    def _test_crm_injection(self) -> list[Finding]:
        findings: list[Finding] = []
        for payload in SQLI_PAYLOADS[:3]:
            resp = self.client.post("/api/crm/clients", json={
                "name": payload,
                "email": "test@test.com",
                "phone": "11999999999",
            }, headers=self.headers)
            if self._has_sql_leak(resp.text, resp.status_code):
                findings.append(Finding(
                    title="SQL Injection na criação de cliente CRM",
                    description="Campo name de POST /api/crm/clients aceita payload SQL.",
                    severity=Severity.HIGH,
                    category="injection",
                    evidence={
                        "endpoint": "POST /api/crm/clients",
                        "field": "name",
                        "payload": payload,
                        "status": resp.status_code,
                    },
                ))
        return findings

    # ── Agent chat ──────────────────────────────────────────────
    def _test_agent_chat_injection(self) -> list[Finding]:
        findings: list[Finding] = []
        for payload in SQLI_PAYLOADS[:2] + COMMAND_INJECTION_PAYLOADS[:2]:
            resp = self.client.post(
                "/api/agents/contabilidade/execute",
                json={"action": "smart_chat", "message": payload},
                headers=self.headers,
            )
            if self._has_sql_leak(resp.text, resp.status_code):
                findings.append(Finding(
                    title="Injection via chat de agente",
                    description="Mensagem enviada ao agente causa erro de banco/sistema.",
                    severity=Severity.MEDIUM,
                    category="injection",
                    evidence={
                        "endpoint": "POST /api/agents/contabilidade/execute",
                        "payload": payload,
                        "status": resp.status_code,
                    },
                ))
        return findings

    # ── Helpers ─────────────────────────────────────────────────
    @staticmethod
    def _has_sql_leak(body: str, status_code: int) -> bool:
        """Detecta se a resposta vaza informações de banco."""
        lower = body.lower()
        # 500 com assinatura de SQL = vazamento claro
        if status_code == 500:
            return any(sig in lower for sig in _SQL_ERROR_SIGNATURES)
        # Respostas 200/400/401 com traces de SQL também contam
        return any(sig in lower for sig in _SQL_ERROR_SIGNATURES if sig != "internal server error")
