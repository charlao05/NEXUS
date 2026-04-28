"""
AutomationLogger — Audit log estruturado em estilo OWASP para automacao.
==========================================================================
Loga eventos de automacao em JSON estruturado com:
- correlation_id (task_id) para correlacao entre nos
- user_id, agent_type para contexto de seguranca
- action, target, result, duration_ms
- risk_level alinhado com policies.py
- timestamp ISO 8601 UTC
- mascaramento automatico de segredos (reusa _SecretSanitizer existente)

Saida:
- Console (formato humano via logger normal)
- Arquivo logs/automation_audit.jsonl (1 evento por linha, formato JSON)
- Sentry breadcrumb para eventos HIGH/CRITICAL

Eventos cobertos:
- task_started, task_completed, task_failed
- action_planned, action_blocked, action_executed, action_failed
- sensitive_screen_detected, awaiting_user_input
- circuit_open, circuit_closed
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

# Reusar sanitizador de segredos
try:
    from utils.logging_utils import _SecretSanitizer, _sanitize
except ImportError:
    from .logging_utils import _SecretSanitizer, _sanitize

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context (correlation_id propagado entre nos do orquestrador)
# ---------------------------------------------------------------------------

_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
_user_id: ContextVar[Optional[int]] = ContextVar("user_id", default=None)
_agent_type: ContextVar[Optional[str]] = ContextVar("agent_type", default=None)


def set_context(
    correlation_id: Optional[str] = None,
    user_id: Optional[int] = None,
    agent_type: Optional[str] = None,
) -> None:
    """Define contexto para os proximos eventos do thread/coroutine."""
    if correlation_id is not None:
        _correlation_id.set(correlation_id)
    if user_id is not None:
        _user_id.set(user_id)
    if agent_type is not None:
        _agent_type.set(agent_type)


def get_correlation_id() -> str:
    """Retorna correlation_id atual ou gera um novo."""
    cid = _correlation_id.get()
    if cid is None:
        cid = f"corr_{uuid.uuid4().hex[:12]}"
        _correlation_id.set(cid)
    return cid


def clear_context() -> None:
    """Limpa contexto (chamar ao final de cada task)."""
    _correlation_id.set(None)
    _user_id.set(None)
    _agent_type.set(None)


# ---------------------------------------------------------------------------
# Audit logger (JSONL file)
# ---------------------------------------------------------------------------

_AUDIT_LOG_FILE = Path("logs/automation_audit.jsonl")
_AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_audit_logger: Optional[logging.Logger] = None
_audit_lock = threading.Lock()


def _get_audit_logger() -> logging.Logger:
    """Logger dedicado para o arquivo JSONL. Singleton thread-safe."""
    global _audit_logger
    if _audit_logger is not None:
        return _audit_logger

    with _audit_lock:
        if _audit_logger is not None:
            return _audit_logger

        log = logging.getLogger("nexus.automation.audit")
        log.setLevel(logging.INFO)
        log.propagate = False

        if not log.handlers:
            handler = RotatingFileHandler(
                _AUDIT_LOG_FILE,
                maxBytes=10_000_000,  # 10 MB
                backupCount=5,
                encoding="utf-8",
            )
            handler.setLevel(logging.INFO)
            # Formato: apenas o JSON puro (mensagem ja serializada)
            handler.setFormatter(logging.Formatter("%(message)s"))
            handler.addFilter(_SecretSanitizer())
            log.addHandler(handler)

        _audit_logger = log
        return log


# ---------------------------------------------------------------------------
# Sentry integration (breadcrumb opcional)
# ---------------------------------------------------------------------------

def _sentry_breadcrumb(event: dict[str, Any]) -> None:
    """Adiciona breadcrumb no Sentry se configurado."""
    try:
        import sentry_sdk
        sentry_sdk.add_breadcrumb(
            category="automation",
            message=event.get("event_type", "automation_event"),
            level=_risk_to_sentry_level(event.get("risk_level", "low")),
            data={
                k: v for k, v in event.items()
                if k not in ("timestamp",) and v is not None
            },
        )
    except Exception:
        pass


def _risk_to_sentry_level(risk: str) -> str:
    """Mapeia risk_level para nivel Sentry."""
    mapping = {
        "low": "info",
        "medium": "warning",
        "high": "warning",
        "critical": "error",
    }
    return mapping.get(risk.lower(), "info")


# ---------------------------------------------------------------------------
# AutomationLogger — API publica
# ---------------------------------------------------------------------------

class AutomationLogger:
    """Audit logger estruturado para eventos de automacao.

    Uso:
        from utils.automation_logger import AutomationLogger, set_context

        set_context(correlation_id="task_xyz", user_id=42, agent_type="browser")
        AutomationLogger.task_started(goal="Consultar CPF na Receita")
        AutomationLogger.action_executed(
            tool="browser_navigate",
            target="https://www.gov.br/...",
            risk="medium",
            duration_ms=1200,
            success=True,
        )
        AutomationLogger.task_completed(actions_count=5, status="completed")
    """

    @staticmethod
    def _emit(event_type: str, risk: str = "low", **fields: Any) -> dict[str, Any]:
        """Emite evento estruturado para arquivo JSONL + console."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "correlation_id": _correlation_id.get(),
            "user_id": _user_id.get(),
            "agent_type": _agent_type.get(),
            "risk_level": risk,
        }
        # Mesclar campos extras (filtrando None)
        for k, v in fields.items():
            if v is not None:
                event[k] = v

        # Sanitizar strings em valores
        for k, v in list(event.items()):
            if isinstance(v, str):
                event[k] = _sanitize(v)

        # 1. Audit file (JSONL)
        try:
            audit = _get_audit_logger()
            audit.info(json.dumps(event, ensure_ascii=False, default=str))
        except Exception as e:
            logger.warning(f"Falha ao escrever audit log: {e}")

        # 2. Console (formato humano)
        msg = AutomationLogger._format_human(event)
        if risk in ("high", "critical"):
            logger.warning(msg)
        else:
            logger.info(msg)

        # 3. Sentry breadcrumb (best-effort)
        if risk in ("medium", "high", "critical"):
            _sentry_breadcrumb(event)

        return event

    @staticmethod
    def _format_human(event: dict[str, Any]) -> str:
        """Formato curto para console."""
        cid = event.get("correlation_id", "")
        cid_short = cid[-8:] if cid else "no-corr"
        evt = event.get("event_type", "?")
        risk = event.get("risk_level", "")
        user = event.get("user_id")

        extras = []
        for k in ("tool", "target", "domain", "duration_ms", "success", "reason"):
            if k in event and event[k] is not None:
                v = event[k]
                if isinstance(v, str) and len(v) > 80:
                    v = v[:77] + "..."
                extras.append(f"{k}={v}")

        return (
            f"[audit:{cid_short}] {evt} risk={risk} user={user} "
            + " ".join(extras)
        )

    # ------------------------------------------------------------------
    # Eventos: tarefa
    # ------------------------------------------------------------------

    @staticmethod
    def task_started(goal: str, max_iterations: int = 10, **kw: Any) -> None:
        AutomationLogger._emit(
            "task_started",
            risk="low",
            goal=goal[:300],
            max_iterations=max_iterations,
            **kw,
        )

    @staticmethod
    def task_completed(
        status: str,
        actions_count: int = 0,
        duration_ms: Optional[int] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "task_completed",
            risk="low",
            status=status,
            actions_count=actions_count,
            duration_ms=duration_ms,
            **kw,
        )

    @staticmethod
    def task_failed(
        error: str,
        status: str = "failed",
        duration_ms: Optional[int] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "task_failed",
            risk="high",
            status=status,
            error=str(error)[:500],
            duration_ms=duration_ms,
            **kw,
        )

    # ------------------------------------------------------------------
    # Eventos: acoes individuais
    # ------------------------------------------------------------------

    @staticmethod
    def action_planned(
        tool: str,
        risk: str = "low",
        rationale: Optional[str] = None,
        target: Optional[str] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "action_planned",
            risk=risk,
            tool=tool,
            target=_short(target),
            rationale=_short(rationale),
            **kw,
        )

    @staticmethod
    def action_executed(
        tool: str,
        risk: str = "low",
        target: Optional[str] = None,
        success: bool = True,
        duration_ms: Optional[int] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "action_executed",
            risk=risk,
            tool=tool,
            target=_short(target),
            success=success,
            duration_ms=duration_ms,
            **kw,
        )

    @staticmethod
    def action_failed(
        tool: str,
        error: str,
        risk: str = "medium",
        target: Optional[str] = None,
        attempt: Optional[int] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "action_failed",
            risk=risk,
            tool=tool,
            target=_short(target),
            error=str(error)[:300],
            attempt=attempt,
            success=False,
            **kw,
        )

    @staticmethod
    def action_blocked(
        tool: str,
        reason: str,
        risk: str = "high",
        target: Optional[str] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "action_blocked",
            risk=risk,
            tool=tool,
            target=_short(target),
            reason=reason[:200],
            **kw,
        )

    @staticmethod
    def action_retried(
        tool: str,
        attempt: int,
        error: str,
        target: Optional[str] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "action_retried",
            risk="medium",
            tool=tool,
            attempt=attempt,
            target=_short(target),
            error=str(error)[:200],
            **kw,
        )

    # ------------------------------------------------------------------
    # Eventos: human-in-the-loop / seguranca
    # ------------------------------------------------------------------

    @staticmethod
    def sensitive_screen_detected(
        domain: str,
        fields: list[str],
        url: Optional[str] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "sensitive_screen_detected",
            risk="high",
            domain=domain,
            fields_detected=fields[:10],
            url=_short(url),
            **kw,
        )

    @staticmethod
    def awaiting_user_input(
        reason: str,
        url: Optional[str] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "awaiting_user_input",
            risk="medium",
            reason=reason[:200],
            url=_short(url),
            **kw,
        )

    @staticmethod
    def approval_required(
        tool: str,
        risk: str = "high",
        message: Optional[str] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "approval_required",
            risk=risk,
            tool=tool,
            message=_short(message),
            **kw,
        )

    @staticmethod
    def approval_granted(tool: str, **kw: Any) -> None:
        AutomationLogger._emit(
            "approval_granted",
            risk="medium",
            tool=tool,
            **kw,
        )

    @staticmethod
    def approval_denied(tool: str, reason: Optional[str] = None, **kw: Any) -> None:
        AutomationLogger._emit(
            "approval_denied",
            risk="high",
            tool=tool,
            reason=_short(reason),
            **kw,
        )

    # ------------------------------------------------------------------
    # Eventos: infraestrutura
    # ------------------------------------------------------------------

    @staticmethod
    def circuit_state_changed(
        domain: str,
        from_state: str,
        to_state: str,
        failures: Optional[int] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "circuit_state_changed",
            risk="high" if to_state == "open" else "medium",
            domain=domain,
            from_state=from_state,
            to_state=to_state,
            failures=failures,
            **kw,
        )

    @staticmethod
    def session_acquired(
        proxy: Optional[str] = None,
        active_sessions: Optional[int] = None,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "session_acquired",
            risk="low",
            using_proxy=bool(proxy),
            active_sessions=active_sessions,
            **kw,
        )

    @staticmethod
    def session_released(
        cookies_saved: int = 0,
        closed: bool = False,
        **kw: Any,
    ) -> None:
        AutomationLogger._emit(
            "session_released",
            risk="low",
            cookies_saved=cookies_saved,
            closed=closed,
            **kw,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _short(s: Optional[str], maxlen: int = 200) -> Optional[str]:
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= maxlen else s[: maxlen - 3] + "..."


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

class TaskContext:
    """Context manager para rastreamento de uma task com correlation_id.

    Uso:
        with TaskContext(task_id="task_xyz", user_id=42, agent_type="browser"):
            AutomationLogger.task_started(goal="...")
            ...
    """

    def __init__(
        self,
        task_id: Optional[str] = None,
        user_id: Optional[int] = None,
        agent_type: Optional[str] = None,
    ):
        self.task_id = task_id or f"task_{uuid.uuid4().hex[:12]}"
        self.user_id = user_id
        self.agent_type = agent_type
        self._prev_corr: Optional[str] = None
        self._prev_user: Optional[int] = None
        self._prev_agent: Optional[str] = None
        self._start: float = 0

    def __enter__(self) -> TaskContext:
        self._prev_corr = _correlation_id.get()
        self._prev_user = _user_id.get()
        self._prev_agent = _agent_type.get()
        _correlation_id.set(self.task_id)
        if self.user_id is not None:
            _user_id.set(self.user_id)
        if self.agent_type is not None:
            _agent_type.set(self.agent_type)
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Restaurar contexto anterior
        _correlation_id.set(self._prev_corr)
        _user_id.set(self._prev_user)
        _agent_type.set(self._prev_agent)
