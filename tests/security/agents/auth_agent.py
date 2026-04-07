"""
Auth Agent — Testa vulnerabilidades de autenticação e autorização
==================================================================
Cobre bypass de JWT, escalação de privilégios, tokens expirados,
brute-force de login, e endpoints sem auth.

Alinhado ao OWASP A01:2021 — Broken Access Control
e A07:2021 — Identification and Authentication Failures.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from fastapi.testclient import TestClient

from .base import Finding, SecurityAgent, Severity


class AuthAgent(SecurityAgent):
    """Testa autenticação, autorização e controle de acesso."""

    name = "auth"
    category = "auth"

    def __init__(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str] | None = None,
        user_id: int = 1,
    ):
        self.client = client
        self.headers = auth_headers
        self.admin_headers = admin_headers or auth_headers
        self.user_id = user_id

    def run(self) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._test_no_auth_endpoints())
        findings.extend(self._test_forged_jwt())
        findings.extend(self._test_expired_token())
        findings.extend(self._test_algorithm_confusion())
        findings.extend(self._test_empty_bearer())
        findings.extend(self._test_login_brute_force_timing())
        findings.extend(self._test_admin_endpoints_without_admin_role())
        findings.extend(self._test_password_in_response())
        return findings

    # ── Endpoints sem auth ──────────────────────────────────────
    def _test_no_auth_endpoints(self) -> list[Finding]:
        """Verifica se endpoints sensíveis estão protegidos."""
        findings: list[Finding] = []
        protected_endpoints = [
            ("GET", "/api/auth/me"),
            ("GET", "/api/auth/my-limits"),
            ("GET", "/api/auth/feedbacks"),
            ("GET", "/api/auth/export-my-data"),
            ("DELETE", "/api/auth/delete-account"),
            ("GET", "/api/crm/clients"),
            ("GET", "/api/crm/pipeline"),
            ("GET", "/api/crm/financial-summary"),
            ("GET", "/api/analytics/dashboard"),
            ("GET", "/api/agents/list"),
            ("GET", "/api/chat/history/contabilidade"),
        ]
        for method, path in protected_endpoints:
            if method == "GET":
                resp = self.client.get(path)
            elif method == "DELETE":
                resp = self.client.delete(path)
            else:
                resp = self.client.post(path, json={})

            # 404 é aceitável — rota não existe, não houve bypass de autenticação
            if resp.status_code not in (401, 403, 404, 405, 307):
                findings.append(Finding(
                    title=f"Endpoint sem autenticação: {method} {path}",
                    description=f"Retornou {resp.status_code} sem header Authorization.",
                    severity=Severity.HIGH,
                    category="auth",
                    evidence={
                        "endpoint": f"{method} {path}",
                        "status": resp.status_code,
                        "response_snippet": resp.text[:200],
                    },
                ))
        return findings

    # ── JWT forjado ─────────────────────────────────────────────
    def _test_forged_jwt(self) -> list[Finding]:
        """Tenta acessar /me com JWT assinado com chave errada."""
        findings: list[Finding] = []
        forged = pyjwt.encode(
            {
                "user_id": self.user_id,
                "email": "hacker@evil.com",
                "plan": "completo",
                "exp": datetime.now(timezone.utc) + timedelta(hours=24),
                "iat": datetime.now(timezone.utc),
            },
            "chave-falsa-do-atacante",
            algorithm="HS256",
        )
        resp = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {forged}"},
        )
        if resp.status_code == 200:
            findings.append(Finding(
                title="JWT forjado aceito pelo backend",
                description="Token assinado com chave arbitrária foi aceito. JWT_SECRET comprometido ou validação ausente.",
                severity=Severity.CRITICAL,
                category="auth",
                evidence={
                    "endpoint": "GET /api/auth/me",
                    "forged_token_key": "chave-falsa-do-atacante",
                    "status": resp.status_code,
                },
            ))
        return findings

    # ── Token expirado ──────────────────────────────────────────
    def _test_expired_token(self) -> list[Finding]:
        """Verifica que tokens expirados são rejeitados."""
        findings: list[Finding] = []
        expired = pyjwt.encode(
            {
                "user_id": self.user_id,
                "email": "test@test.com",
                "plan": "free",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            },
            # Usa chave de dev — em test env é "dev-only-secret-change-in-production"
            "dev-only-secret-change-in-production",
            algorithm="HS256",
        )
        resp = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired}"},
        )
        if resp.status_code == 200:
            findings.append(Finding(
                title="Token expirado aceito pelo backend",
                description="JWT com exp no passado retornou 200 — validação de expiração ausente.",
                severity=Severity.HIGH,
                category="auth",
                evidence={
                    "endpoint": "GET /api/auth/me",
                    "status": resp.status_code,
                },
            ))
        return findings

    # ── Algorithm confusion (none attack) ───────────────────────
    def _test_algorithm_confusion(self) -> list[Finding]:
        """Tenta bypass com algorithm=none."""
        findings: list[Finding] = []
        import base64
        import json

        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()

        payload_data = base64.urlsafe_b64encode(
            json.dumps({
                "user_id": self.user_id,
                "email": "none@evil.com",
                "plan": "completo",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
                "iat": int(datetime.now(timezone.utc).timestamp()),
            }).encode()
        ).rstrip(b"=").decode()

        none_token = f"{header}.{payload_data}."

        resp = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {none_token}"},
        )
        if resp.status_code == 200:
            findings.append(Finding(
                title="JWT alg=none aceito (algorithm confusion)",
                description="Backend aceita tokens com algorithm='none' — bypass total de autenticação.",
                severity=Severity.CRITICAL,
                category="auth",
                evidence={
                    "endpoint": "GET /api/auth/me",
                    "attack": "algorithm_confusion",
                    "status": resp.status_code,
                },
            ))
        return findings

    # ── Bearer vazio/malformado ─────────────────────────────────
    def _test_empty_bearer(self) -> list[Finding]:
        findings: list[Finding] = []
        bad_headers = [
            {"Authorization": "Bearer "},
            {"Authorization": "Bearer null"},
            {"Authorization": "Bearer undefined"},
            {"Authorization": "Basic dGVzdDp0ZXN0"},
            {"Authorization": ""},
        ]
        for h in bad_headers:
            resp = self.client.get("/api/auth/me", headers=h)
            if resp.status_code == 200:
                findings.append(Finding(
                    title=f"Auth bypass com header: {list(h.values())[0][:40]}",
                    description="Endpoint /me aceitou header Authorization inválido.",
                    severity=Severity.CRITICAL,
                    category="auth",
                    evidence={"header": h, "status": resp.status_code},
                ))
        return findings

    # ── Timing attack no login ──────────────────────────────────
    def _test_login_brute_force_timing(self) -> list[Finding]:
        """Verifica se login tem timing constante (user existente vs inexistente)."""
        findings: list[Finding] = []

        # Mede tempo para email inexistente
        times_no_user: list[float] = []
        for _ in range(3):
            start = time.monotonic()
            self.client.post("/api/auth/login", json={
                "email": "naoexiste_timing@test.com",
                "password": "QualquerSenha@123",
            })
            times_no_user.append(time.monotonic() - start)

        # Mede tempo para email existente + senha errada
        times_wrong_pwd: list[float] = []
        for _ in range(3):
            start = time.monotonic()
            self.client.post("/api/auth/login", json={
                "email": "timing_test@nexus.com",
                "password": "SenhaErrada@999",
            })
            times_wrong_pwd.append(time.monotonic() - start)

        avg_no_user = sum(times_no_user) / len(times_no_user)
        avg_wrong_pwd = sum(times_wrong_pwd) / len(times_wrong_pwd)

        # Se a diferença for > 100ms, pode indicar timing leak
        diff = abs(avg_no_user - avg_wrong_pwd)
        if diff > 0.15:
            findings.append(Finding(
                title="Timing leak no login (user enumeration)",
                description=f"Diferença média de {diff*1000:.0f}ms entre user existente e inexistente. "
                            "Atacante pode enumerar emails válidos.",
                severity=Severity.MEDIUM,
                category="auth",
                evidence={
                    "avg_no_user_ms": round(avg_no_user * 1000, 1),
                    "avg_wrong_pwd_ms": round(avg_wrong_pwd * 1000, 1),
                    "diff_ms": round(diff * 1000, 1),
                },
            ))
        return findings

    # ── Endpoints admin sem role admin ──────────────────────────
    def _test_admin_endpoints_without_admin_role(self) -> list[Finding]:
        """Testa se endpoints /admin podem ser acessados por user normal."""
        findings: list[Finding] = []
        admin_endpoints = [
            ("POST", "/api/auth/admin/switch-plan", {"email": "test@test.com", "new_plan": "completo"}),
            ("GET", "/api/admin/users", None),
            ("GET", "/api/admin/stats", None),
        ]
        for method, path, body in admin_endpoints:
            if method == "GET":
                resp = self.client.get(path, headers=self.headers)
            else:
                resp = self.client.post(path, json=body or {}, headers=self.headers)

            if resp.status_code == 200:
                findings.append(Finding(
                    title=f"Escalação de privilégio: {method} {path}",
                    description="User sem role admin acessou endpoint administrativo.",
                    severity=Severity.CRITICAL,
                    category="auth",
                    evidence={
                        "endpoint": f"{method} {path}",
                        "status": resp.status_code,
                        "response_snippet": resp.text[:200],
                    },
                ))
        return findings

    # ── Senha no response ───────────────────────────────────────
    def _test_password_in_response(self) -> list[Finding]:
        """Verifica que nenhum endpoint retorna password_hash ou senha."""
        findings: list[Finding] = []
        endpoints = [
            ("GET", "/api/auth/me"),
            ("GET", "/api/auth/export-my-data"),
        ]
        for method, path in endpoints:
            resp = self.client.get(path, headers=self.headers)
            lower = resp.text.lower()
            if any(kw in lower for kw in ["password_hash", '"password":', "$2b$12$"]):
                findings.append(Finding(
                    title=f"Password hash vazado em {path}",
                    description="Endpoint retorna hash de senha — exposição de dados sensíveis.",
                    severity=Severity.HIGH,
                    category="auth",
                    evidence={
                        "endpoint": f"{method} {path}",
                        "status": resp.status_code,
                        "leak_detected": True,
                    },
                ))
        return findings
