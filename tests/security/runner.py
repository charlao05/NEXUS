"""
Runner / Orquestrador de Agentes de Segurança
===============================================
Executa todos os agentes em paralelo (estilo Shannon) e agrega findings.
Pode ser usado via pytest OU como script standalone.

Uso:
    # Via pytest (recomendado — integração VS Code):
    pytest tests/security/ -v

    # Via script:
    python -m tests.security.runner
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from .agents.base import Finding, SecurityAgent, Severity


def run_all_agents(agents: list[SecurityAgent]) -> list[Finding]:
    """Executa todos os agentes em paralelo e retorna findings consolidados."""
    findings: list[Finding] = []
    with ThreadPoolExecutor(max_workers=min(len(agents), 4)) as executor:
        future_to_agent = {executor.submit(a.run): a for a in agents}
        for future in as_completed(future_to_agent):
            agent = future_to_agent[future]
            try:
                agent_findings = future.result()
                findings.extend(agent_findings)
            except Exception as exc:
                findings.append(Finding(
                    title=f"Agente {agent.name} falhou com exceção",
                    description=str(exc),
                    severity=Severity.INFO,
                    category="runner",
                    evidence={"agent": agent.name, "error": str(exc)},
                ))
    return findings


def generate_report(findings: list[Finding], output_dir: str = "logs") -> str:
    """Gera relatório JSON com todos os findings."""
    Path(output_dir).mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(output_dir) / f"security_report_{ts}.json"

    report = {
        "generated_at": datetime.now().isoformat(),
        "total_findings": len(findings),
        "critical_count": sum(1 for f in findings if f.severity == Severity.CRITICAL),
        "high_count": sum(1 for f in findings if f.severity == Severity.HIGH),
        "medium_count": sum(1 for f in findings if f.severity == Severity.MEDIUM),
        "low_count": sum(1 for f in findings if f.severity == Severity.LOW),
        "findings": [
            {
                "title": f.title,
                "description": f.description,
                "severity": f.severity.value,
                "category": f.category,
                "evidence": f.evidence,
            }
            for f in sorted(findings, key=lambda x: list(Severity).index(x.severity))
        ],
    }

    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)
