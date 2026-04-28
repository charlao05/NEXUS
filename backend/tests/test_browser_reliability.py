"""
Testes de integracao da infraestrutura de reliability do browser.

Cobre:
- DomainCircuitBreaker: state machine completo (CLOSED -> OPEN -> HALF_OPEN)
- SessionStore: save/load/clear, filtragem por dominio, TTL em memoria
- AutomationLogger: ContextVar isolation entre tasks, JSONL output

Nao testa BrowserPool diretamente porque ele requer Playwright + Chromium
instalados. O teste do pool via mocks fica em test_browser_pool_mock.py
(adicionavel quando houver runner com Playwright).
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures: forçar fallback in-memory (sem depender de Redis em CI)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_redis(monkeypatch):
    """Garante que get_redis() retorna None nos testes — fallback in-memory."""
    def _no_redis():
        return None
    monkeypatch.setattr(
        "app.api.redis_client.get_redis", _no_redis, raising=False
    )


@pytest.fixture
def fresh_breaker():
    """Singleton novo do circuit breaker, com thresholds rapidos para teste."""
    from browser.circuit_breaker import DomainCircuitBreaker

    DomainCircuitBreaker.reset_instance()
    breaker = DomainCircuitBreaker(
        failure_threshold=3,
        recovery_timeout=2,  # 2s para HALF_OPEN (1s causa retry_in_seconds=0)
        success_threshold=2,
    )
    DomainCircuitBreaker._instance = breaker
    yield breaker
    DomainCircuitBreaker.reset_instance()


@pytest.fixture
def fresh_session_store():
    from browser.session_store import SessionStore
    SessionStore.reset_instance()
    store = SessionStore.get_instance()
    yield store
    SessionStore.reset_instance()


# ---------------------------------------------------------------------------
# Circuit Breaker — state machine
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_starts_closed_for_unknown_domain(self, fresh_breaker):
        """Dominio nunca visto comeca CLOSED — chamada permitida."""
        fresh_breaker.check("https://www.gov.br/receita")
        assert fresh_breaker.is_open("www.gov.br") is False

    def test_opens_after_threshold_failures(self, fresh_breaker):
        """3 falhas consecutivas → estado OPEN, chamadas seguintes rejeitadas."""
        domain = "receita.fazenda.gov.br"
        for _ in range(3):
            fresh_breaker.record_failure(domain)

        from browser.circuit_breaker import CircuitOpenError

        assert fresh_breaker.is_open(domain) is True
        with pytest.raises(CircuitOpenError) as exc:
            fresh_breaker.check(domain)
        assert exc.value.domain == domain
        assert exc.value.retry_in_seconds > 0

    def test_does_not_open_below_threshold(self, fresh_breaker):
        """2 falhas (abaixo do threshold=3) → ainda CLOSED."""
        domain = "test.example.com"
        fresh_breaker.record_failure(domain)
        fresh_breaker.record_failure(domain)
        assert fresh_breaker.is_open(domain) is False

    def test_success_resets_failure_counter_in_closed(self, fresh_breaker):
        """Sucesso em CLOSED zera contador — proximas falhas comecam do zero."""
        domain = "intermitent.example.com"
        fresh_breaker.record_failure(domain)
        fresh_breaker.record_failure(domain)
        fresh_breaker.record_success(domain)  # zera

        # Mais 2 falhas ainda nao deve abrir (precisa 3 consecutivas)
        fresh_breaker.record_failure(domain)
        fresh_breaker.record_failure(domain)
        assert fresh_breaker.is_open(domain) is False

    def test_open_transitions_to_half_open_after_recovery_timeout(self, fresh_breaker):
        """OPEN → HALF_OPEN apos recovery_timeout — uma chamada de teste passa."""
        domain = "recovery.example.com"
        for _ in range(3):
            fresh_breaker.record_failure(domain)
        assert fresh_breaker.is_open(domain) is True

        time.sleep(2.05)  # > recovery_timeout=1s

        # Apos timeout, check() deve permitir (transicao para HALF_OPEN)
        fresh_breaker.check(domain)  # nao levanta
        info = fresh_breaker.stats(domain)
        assert info["state"] == "half_open"

    def test_half_open_closes_after_success_threshold(self, fresh_breaker):
        """HALF_OPEN com 2 sucessos consecutivos → CLOSED."""
        domain = "halfopen-success.example.com"
        for _ in range(3):
            fresh_breaker.record_failure(domain)
        time.sleep(2.05)
        fresh_breaker.check(domain)  # transiciona para HALF_OPEN

        fresh_breaker.record_success(domain)
        fresh_breaker.record_success(domain)
        info = fresh_breaker.stats(domain)
        assert info["state"] == "closed"
        assert info["failures"] == 0

    def test_half_open_failure_reopens_immediately(self, fresh_breaker):
        """HALF_OPEN: qualquer falha re-abre imediatamente."""
        domain = "halfopen-fail.example.com"
        for _ in range(3):
            fresh_breaker.record_failure(domain)
        time.sleep(2.05)
        fresh_breaker.check(domain)  # transiciona para HALF_OPEN

        fresh_breaker.record_failure(domain)  # re-abre

        from browser.circuit_breaker import CircuitOpenError
        with pytest.raises(CircuitOpenError):
            fresh_breaker.check(domain)

    def test_force_close_clears_state(self, fresh_breaker):
        """force_close (admin) volta ao estado CLOSED instantaneamente."""
        domain = "stuck.example.com"
        for _ in range(5):
            fresh_breaker.record_failure(domain)
        assert fresh_breaker.is_open(domain) is True

        fresh_breaker.force_close(domain)
        assert fresh_breaker.is_open(domain) is False

    def test_isolation_between_domains(self, fresh_breaker):
        """Falhas em um dominio NAO afetam outro."""
        for _ in range(3):
            fresh_breaker.record_failure("site-a.com")
        assert fresh_breaker.is_open("site-a.com") is True
        assert fresh_breaker.is_open("site-b.com") is False

    def test_normalize_extracts_domain_from_url(self, fresh_breaker):
        """check() aceita URL completa, normaliza para netloc."""
        for _ in range(3):
            fresh_breaker.record_failure("https://www.gov.br/path?q=1")
        # Mesmo dominio via URL diferente deve estar aberto
        assert fresh_breaker.is_open("https://www.gov.br/outro") is True


# ---------------------------------------------------------------------------
# SessionStore — persistencia de cookies
# ---------------------------------------------------------------------------

class TestSessionStore:
    def test_save_and_load_roundtrip(self, fresh_session_store):
        """Save → load retorna mesmos cookies."""
        cookies = [
            {"name": "session_id", "value": "abc123", "domain": "gov.br"},
            {"name": "csrf", "value": "tok", "domain": "gov.br"},
        ]
        fresh_session_store.save(user_id=42, domain="gov.br", cookies=cookies)
        loaded = fresh_session_store.load(user_id=42, domain="gov.br")
        assert len(loaded) == 2
        assert {c["name"] for c in loaded} == {"session_id", "csrf"}

    def test_load_returns_empty_for_unknown_user(self, fresh_session_store):
        assert fresh_session_store.load(user_id=999, domain="gov.br") == []

    def test_isolation_between_users(self, fresh_session_store):
        """User 1 e User 2 tem stores separados — nao vazam cookies."""
        c1 = [{"name": "u1", "value": "v1", "domain": "site.com"}]
        c2 = [{"name": "u2", "value": "v2", "domain": "site.com"}]
        fresh_session_store.save(1, "site.com", c1)
        fresh_session_store.save(2, "site.com", c2)
        assert fresh_session_store.load(1, "site.com")[0]["name"] == "u1"
        assert fresh_session_store.load(2, "site.com")[0]["name"] == "u2"

    def test_clear_removes_only_user_domain(self, fresh_session_store):
        """clear(user, domain) remove apenas aquele par."""
        fresh_session_store.save(1, "a.com", [{"name": "k", "value": "v", "domain": "a.com"}])
        fresh_session_store.save(1, "b.com", [{"name": "k", "value": "v", "domain": "b.com"}])

        fresh_session_store.clear(user_id=1, domain="a.com")
        assert fresh_session_store.load(1, "a.com") == []
        assert len(fresh_session_store.load(1, "b.com")) == 1

    def test_clear_all_for_user_removes_every_domain(self, fresh_session_store):
        """clear(user) sem domain remove tudo do usuario."""
        fresh_session_store.save(1, "a.com", [{"name": "k", "value": "v", "domain": "a.com"}])
        fresh_session_store.save(1, "b.com", [{"name": "k", "value": "v", "domain": "b.com"}])

        removed = fresh_session_store.clear(user_id=1)
        assert removed == 2
        assert fresh_session_store.load(1, "a.com") == []
        assert fresh_session_store.load(1, "b.com") == []

    def test_filter_drops_cookies_from_other_domains(self, fresh_session_store):
        """Cookies de dominios nao relacionados sao filtrados."""
        cookies = [
            {"name": "ok", "value": "v", "domain": "gov.br"},
            {"name": "leak", "value": "v", "domain": "facebook.com"},
        ]
        fresh_session_store.save(1, "gov.br", cookies)
        loaded = fresh_session_store.load(1, "gov.br")
        names = {c["name"] for c in loaded}
        assert "ok" in names
        assert "leak" not in names

    def test_save_no_cookies_is_noop(self, fresh_session_store):
        """save() com lista vazia nao cria entrada."""
        fresh_session_store.save(1, "site.com", [])
        assert fresh_session_store.load(1, "site.com") == []

    def test_load_all_aggregates_user_domains(self, fresh_session_store):
        """load_all retorna cookies de todos os dominios do usuario."""
        fresh_session_store.save(1, "a.com", [{"name": "ka", "value": "v", "domain": "a.com"}])
        fresh_session_store.save(1, "b.com", [{"name": "kb", "value": "v", "domain": "b.com"}])

        all_cookies = fresh_session_store.load_all(user_id=1)
        names = {c["name"] for c in all_cookies}
        assert names == {"ka", "kb"}

    def test_ttl_expires_in_memory(self, fresh_session_store):
        """TTL expirado em memoria → load retorna vazio (auto-cleanup)."""
        fresh_session_store.save(
            user_id=1,
            domain="ephemeral.com",
            cookies=[{"name": "k", "value": "v", "domain": "ephemeral.com"}],
            ttl_seconds=1,
        )
        # Imediatamente deve carregar
        assert len(fresh_session_store.load(1, "ephemeral.com")) == 1

        time.sleep(1.1)
        assert fresh_session_store.load(1, "ephemeral.com") == []


# ---------------------------------------------------------------------------
# AutomationLogger — ContextVar + JSONL output
# ---------------------------------------------------------------------------

class TestAutomationLogger:
    @pytest.fixture(autouse=True)
    def _redirect_audit_log(self, tmp_path, monkeypatch):
        """Redireciona o audit log para um arquivo temporario.

        IMPORTANTE: logging.getLogger() retorna a mesma instancia globalmente,
        entao precisamos limpar handlers entre testes (senao apontam pra
        tmp_path do teste anterior, que ja foi removido).
        """
        import logging
        from utils import automation_logger as al

        named_log = logging.getLogger("nexus.automation.audit")
        named_log.handlers.clear()  # critico: handlers de testes anteriores
        al._audit_logger = None

        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(al, "_AUDIT_LOG_FILE", log_path)
        yield log_path

        # Cleanup: fechar handlers explicitamente (Windows file lock)
        for h in named_log.handlers:
            try:
                h.close()
            except Exception:
                pass
        named_log.handlers.clear()
        al._audit_logger = None

    def _read_events(self, log_path: Path) -> list[dict]:
        """Le eventos JSONL do arquivo de teste."""
        if not log_path.exists():
            return []
        events = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
        return events

    def test_emits_event_with_required_fields(self, _redirect_audit_log):
        from utils.automation_logger import AutomationLogger, set_context, clear_context

        clear_context()
        set_context(correlation_id="task_test_001", user_id=42, agent_type="browser")
        AutomationLogger.task_started(goal="Consultar CPF")

        events = self._read_events(_redirect_audit_log)
        assert len(events) == 1
        e = events[0]
        assert e["event_type"] == "task_started"
        assert e["correlation_id"] == "task_test_001"
        assert e["user_id"] == 42
        assert e["agent_type"] == "browser"
        assert "timestamp" in e
        assert e["goal"] == "Consultar CPF"
        clear_context()

    def test_context_isolation_between_tasks(self, _redirect_audit_log):
        """Cada TaskContext preserva o contexto anterior ao sair."""
        from utils.automation_logger import (
            AutomationLogger, TaskContext, set_context, clear_context, _correlation_id
        )

        clear_context()
        set_context(correlation_id="outer", user_id=1, agent_type="x")

        with TaskContext(task_id="inner", user_id=99, agent_type="browser"):
            AutomationLogger.task_started(goal="inner task")
            assert _correlation_id.get() == "inner"

        # Apos sair, contexto externo restaurado
        assert _correlation_id.get() == "outer"

        events = self._read_events(_redirect_audit_log)
        # O evento de inner deve ter correlation_id="inner"
        inner = [e for e in events if e["event_type"] == "task_started"]
        assert inner[0]["correlation_id"] == "inner"
        assert inner[0]["user_id"] == 99
        clear_context()

    def test_action_blocked_marked_high_risk(self, _redirect_audit_log):
        """Acao bloqueada por policy emite evento risk=high."""
        from utils.automation_logger import AutomationLogger, set_context, clear_context

        clear_context()
        set_context(correlation_id="task_block", user_id=1, agent_type="browser")
        AutomationLogger.action_blocked(
            tool="browser_navigate",
            reason="Domain not in allowlist",
            target="https://malicious.example",
        )

        events = self._read_events(_redirect_audit_log)
        assert len(events) == 1
        assert events[0]["event_type"] == "action_blocked"
        assert events[0]["risk_level"] == "high"
        assert events[0]["reason"].startswith("Domain not in allowlist")
        clear_context()

    def test_circuit_state_change_logged(self, _redirect_audit_log):
        from utils.automation_logger import AutomationLogger, clear_context, set_context

        clear_context()
        set_context(correlation_id="task_circuit", user_id=1, agent_type="browser")
        AutomationLogger.circuit_state_changed(
            domain="gov.br",
            from_state="closed",
            to_state="open",
            failures=5,
        )
        events = self._read_events(_redirect_audit_log)
        assert events[0]["event_type"] == "circuit_state_changed"
        assert events[0]["risk_level"] == "high"
        assert events[0]["domain"] == "gov.br"
        clear_context()

    def test_get_correlation_id_generates_when_absent(self):
        from utils.automation_logger import get_correlation_id, clear_context

        clear_context()
        cid = get_correlation_id()
        assert cid.startswith("corr_")
        # Chamada subsequente retorna o mesmo
        assert get_correlation_id() == cid
        clear_context()


# ---------------------------------------------------------------------------
# Smoke: imports do orchestrator/tools/browser nao quebram
# ---------------------------------------------------------------------------

class TestImportSmoke:
    def test_orchestrator_browser_tools_import(self):
        """Garante que rewrite do tools/browser.py nao quebrou imports."""
        from orchestrator.tools import browser as bt

        # Tools publicas precisam existir
        for name in (
            "browser_navigate", "browser_click", "browser_type", "browser_wait",
            "browser_screenshot", "browser_get_text", "browser_get_page_state",
            "shutdown_browser",
        ):
            assert hasattr(bt, name), f"Faltou export: {name}"

    def test_pool_module_imports_without_starting_browser(self):
        """Importar pool.py NAO deve iniciar Playwright (lazy)."""
        from browser import pool
        assert hasattr(pool, "BrowserPool")
        # Apenas a classe — nao chamar acquire()

    def test_circuit_breaker_singleton_thread_safe(self):
        """get_instance() retorna mesma instancia em chamadas concorrentes."""
        from browser.circuit_breaker import DomainCircuitBreaker
        DomainCircuitBreaker.reset_instance()

        instances = []
        import threading
        def _grab():
            instances.append(DomainCircuitBreaker.get_instance())
        threads = [threading.Thread(target=_grab) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Todas devem ser a mesma instancia
        assert all(i is instances[0] for i in instances)
        DomainCircuitBreaker.reset_instance()
