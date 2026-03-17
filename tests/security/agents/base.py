"""
NEXUS Security Agents — Base classes
=====================================
Framework inspirado no Shannon para testes de segurança automatizados.
Cada agente foca em uma categoria de vulnerabilidade (Injection, Auth, IDOR, XSS, etc.)
e produz Findings com evidências reproduzíveis — sem falsos positivos.

Uso:
    agent = SqlInjectionAgent(client, auth_headers)
    findings = agent.run()
    assert not [f for f in findings if f.critical]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Severidade alinhada ao OWASP."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Finding:
    """Resultado de uma vulnerabilidade detectada com evidência reproduzível."""
    title: str
    description: str
    severity: Severity
    category: str  # "injection", "auth", "idor", "xss", "rate_limit", "misc"
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def critical(self) -> bool:
        return self.severity in (Severity.CRITICAL, Severity.HIGH)

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.title}"


class SecurityAgent(ABC):
    """Interface base para todos os agentes de segurança."""

    name: str = "base"
    category: str = "misc"

    @abstractmethod
    def run(self) -> list[Finding]:
        """Executa todos os testes do agente e retorna findings."""
        ...
