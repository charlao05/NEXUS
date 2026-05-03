"""
UsageTracker — Sink in-memory thread-safe para eventos de uso (LLM e automation).

Janela móvel de 48h, agregações sob demanda por user_id/model/agent.
Sem persistência: ao reiniciar o processo, dados perdem-se. Tier 2 adicionará
persistência com tabela LLMUsage/AutomationUsage.

Uso:
    from utils.usage_tracker import UsageTracker
    UsageTracker.record_llm(user_id=42, model="gpt-4o-mini",
                            prompt_tokens=120, completion_tokens=80,
                            duration_ms=347, cost_usd=0.000123)
    UsageTracker.record_automation(user_id=42, agent_type="finance",
                                    tool="navigate", duration_ms=1200,
                                    success=True)

    snap = UsageTracker.snapshot_llm(since_minutes=60*24)
    # Returns: {"by_user": {...}, "by_model": {...}, "totals": {...}}
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional


_MAX_EVENTS = 50_000          # cap de memória; eventos antigos são derrubados
_RETENTION_SECONDS = 48 * 3600  # 48h


@dataclass(frozen=True)
class LLMUsageEvent:
    ts: float
    user_id: int
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_ms: int
    cost_usd: float
    correlation_id: Optional[str] = None
    agent_type: Optional[str] = None


@dataclass(frozen=True)
class AutomationUsageEvent:
    ts: float
    user_id: int
    agent_type: str
    tool: str           # navigate, click, type, screenshot, etc.
    duration_ms: int
    success: bool
    correlation_id: Optional[str] = None


class UsageTracker:
    _lock = threading.RLock()
    _llm_events: "deque[LLMUsageEvent]" = deque(maxlen=_MAX_EVENTS)
    _automation_events: "deque[AutomationUsageEvent]" = deque(maxlen=_MAX_EVENTS)

    @classmethod
    def record_llm(
        cls,
        *,
        user_id: int,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        cost_usd: float,
        correlation_id: Optional[str] = None,
        agent_type: Optional[str] = None,
    ) -> None:
        """Registra uma chamada LLM. NUNCA bloqueia. NUNCA levanta excecao pra fora.
        Em caso de erro interno, suprime e loga warning - instrumentacao nao pode
        derrubar o caminho feliz."""
        try:
            ev = LLMUsageEvent(
                ts=time.time(),
                user_id=int(user_id) if user_id is not None else 0,
                model=str(model or "unknown"),
                prompt_tokens=max(0, int(prompt_tokens or 0)),
                completion_tokens=max(0, int(completion_tokens or 0)),
                total_tokens=max(0, int(prompt_tokens or 0) + int(completion_tokens or 0)),
                duration_ms=max(0, int(duration_ms or 0)),
                cost_usd=max(0.0, float(cost_usd or 0.0)),
                correlation_id=correlation_id,
                agent_type=agent_type,
            )
            with cls._lock:
                cls._llm_events.append(ev)
        except Exception:
            # silenciar — instrumentacao nao pode quebrar caminho feliz
            import logging
            logging.getLogger(__name__).warning("UsageTracker.record_llm falhou", exc_info=True)

    @classmethod
    def record_automation(
        cls,
        *,
        user_id: int,
        agent_type: str,
        tool: str,
        duration_ms: int,
        success: bool,
        correlation_id: Optional[str] = None,
    ) -> None:
        try:
            ev = AutomationUsageEvent(
                ts=time.time(),
                user_id=int(user_id) if user_id is not None else 0,
                agent_type=str(agent_type or "unknown"),
                tool=str(tool or "unknown"),
                duration_ms=max(0, int(duration_ms or 0)),
                success=bool(success),
                correlation_id=correlation_id,
            )
            with cls._lock:
                cls._automation_events.append(ev)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("UsageTracker.record_automation falhou", exc_info=True)

    @classmethod
    def _purge_old(cls) -> None:
        """Remove eventos fora da janela de retencao. Chamado sob _lock."""
        cutoff = time.time() - _RETENTION_SECONDS
        while cls._llm_events and cls._llm_events[0].ts < cutoff:
            cls._llm_events.popleft()
        while cls._automation_events and cls._automation_events[0].ts < cutoff:
            cls._automation_events.popleft()

    @classmethod
    def snapshot_llm(cls, *, since_minutes: int = 60 * 24) -> dict:
        """Snapshot agregado dos ultimos N minutos.

        Retorna estrutura:
        {
            "window_minutes": 1440,
            "events_count": int,
            "totals": {
                "prompt_tokens": int,
                "completion_tokens": int,
                "total_tokens": int,
                "cost_usd": float,
                "calls": int,
                "avg_duration_ms": int,
            },
            "by_user": {user_id: {...mesmo schema dos totals...}},
            "by_model": {model_name: {...mesmo schema...}},
        }
        """
        cutoff = time.time() - max(60, since_minutes) * 60
        with cls._lock:
            cls._purge_old()
            events = [e for e in cls._llm_events if e.ts >= cutoff]

        def _empty():
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                    "cost_usd": 0.0, "calls": 0, "duration_ms_sum": 0}

        totals = _empty()
        by_user: dict[int, dict] = {}
        by_model: dict[str, dict] = {}

        for ev in events:
            for bucket in (totals, by_user.setdefault(ev.user_id, _empty()),
                           by_model.setdefault(ev.model, _empty())):
                bucket["prompt_tokens"] += ev.prompt_tokens
                bucket["completion_tokens"] += ev.completion_tokens
                bucket["total_tokens"] += ev.total_tokens
                bucket["cost_usd"] += ev.cost_usd
                bucket["calls"] += 1
                bucket["duration_ms_sum"] += ev.duration_ms

        def _finalize(b: dict) -> dict:
            calls = b["calls"] or 1
            return {
                "prompt_tokens": b["prompt_tokens"],
                "completion_tokens": b["completion_tokens"],
                "total_tokens": b["total_tokens"],
                "cost_usd": round(b["cost_usd"], 6),
                "calls": b["calls"],
                "avg_duration_ms": int(b["duration_ms_sum"] / calls),
            }

        return {
            "window_minutes": since_minutes,
            "events_count": len(events),
            "totals": _finalize(totals),
            "by_user": {uid: _finalize(b) for uid, b in by_user.items()},
            "by_model": {m: _finalize(b) for m, b in by_model.items()},
        }

    @classmethod
    def snapshot_automation(cls, *, since_minutes: int = 60 * 24) -> dict:
        """Mesmo padrao de snapshot_llm, mas pra automation events.
        Agrega por user_id, agent_type e tool. Inclui taxa de sucesso."""
        cutoff = time.time() - max(60, since_minutes) * 60
        with cls._lock:
            cls._purge_old()
            events = [e for e in cls._automation_events if e.ts >= cutoff]

        def _empty():
            return {"calls": 0, "success": 0, "failure": 0, "duration_ms_sum": 0}

        totals = _empty()
        by_user: dict[int, dict] = {}
        by_agent: dict[str, dict] = {}
        by_tool: dict[str, dict] = {}

        for ev in events:
            for bucket in (totals, by_user.setdefault(ev.user_id, _empty()),
                           by_agent.setdefault(ev.agent_type, _empty()),
                           by_tool.setdefault(ev.tool, _empty())):
                bucket["calls"] += 1
                bucket["success" if ev.success else "failure"] += 1
                bucket["duration_ms_sum"] += ev.duration_ms

        def _finalize(b: dict) -> dict:
            calls = b["calls"] or 1
            return {
                "calls": b["calls"],
                "success": b["success"],
                "failure": b["failure"],
                "success_rate": round(b["success"] / calls, 3),
                "avg_duration_ms": int(b["duration_ms_sum"] / calls),
                "total_duration_ms": b["duration_ms_sum"],
            }

        return {
            "window_minutes": since_minutes,
            "events_count": len(events),
            "totals": _finalize(totals),
            "by_user": {uid: _finalize(b) for uid, b in by_user.items()},
            "by_agent": {a: _finalize(b) for a, b in by_agent.items()},
            "by_tool": {t: _finalize(b) for t, b in by_tool.items()},
        }

    @classmethod
    def reset(cls) -> None:
        """Limpa todos os eventos. Uso: tests."""
        with cls._lock:
            cls._llm_events.clear()
            cls._automation_events.clear()
