"""
BrowserPool — Pool de sessoes isoladas por usuario/task.
=========================================================
Substitui o singleton global `_browser_state` por sessoes isoladas:
- Cada usuario tem seu proprio BrowserContext (cookies, storage, proxy separados)
- Lock por usuario impede duas tasks do mesmo usuario colidirem
- Semaforo global limita sessoes simultaneas (protege RAM do Render)
- TTL automatico fecha sessoes ociosas
- atexit handler garante cleanup mesmo em crash
- Integra com SessionStore para persistir cookies entre tasks

Uso:
    pool = BrowserPool.get_instance()
    session = pool.acquire(user_id=42, task_id="task_abc123")
    page = session.page
    # ... usar page normalmente ...
    pool.release(user_id=42)
"""
from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuracao via env vars
# ---------------------------------------------------------------------------

MAX_SESSIONS = int(os.getenv("BROWSER_POOL_MAX_SESSIONS", "5"))
SESSION_TTL = int(os.getenv("BROWSER_POOL_SESSION_TTL", "600"))  # 10min
CLEANUP_INTERVAL = int(os.getenv("BROWSER_POOL_CLEANUP_INTERVAL", "60"))  # 1min


# ---------------------------------------------------------------------------
# BrowserSession — uma sessao isolada
# ---------------------------------------------------------------------------

@dataclass
class BrowserSession:
    """Sessao isolada de browser para um usuario/task."""
    context: Any  # BrowserContext
    page: Any  # Page
    user_id: int
    task_id: str
    proxy: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    domain: str = ""  # Dominio principal sendo acessado

    def touch(self) -> None:
        """Atualiza timestamp de ultimo uso."""
        self.last_used = time.time()

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_used

    @property
    def is_expired(self) -> bool:
        return self.idle_seconds > SESSION_TTL


# ---------------------------------------------------------------------------
# BrowserPool — gerenciador de sessoes
# ---------------------------------------------------------------------------

class BrowserPool:
    """Pool de sessoes Playwright isoladas por usuario.

    Thread-safe. Singleton via get_instance().
    """

    _instance: Optional[BrowserPool] = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        max_sessions: int = MAX_SESSIONS,
        session_ttl: int = SESSION_TTL,
    ):
        self._pw: Any = None
        self._browser: Any = None
        self._sessions: dict[int, BrowserSession] = {}  # user_id -> session
        self._user_locks: dict[int, threading.RLock] = {}
        self._global_lock = threading.Lock()
        self._semaphore = threading.Semaphore(max_sessions)
        self._max_sessions = max_sessions
        self._session_ttl = session_ttl
        self._shutdown_event = threading.Event()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._started = False

        # Registrar atexit
        atexit.register(self._atexit_cleanup)

    @classmethod
    def get_instance(cls) -> BrowserPool:
        """Retorna singleton do pool. Thread-safe."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset para testes."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.shutdown()
            cls._instance = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_browser(self) -> None:
        """Inicializa Playwright e browser se necessario."""
        if self._browser is not None:
            return

        from browser.playwright_client import create_stealth_browser
        self._pw, self._browser = create_stealth_browser()
        self._started = True

        # Iniciar thread de cleanup
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._shutdown_event.clear()
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                name="browser-pool-cleanup",
                daemon=True,
            )
            self._cleanup_thread.start()

        logger.info(
            f"BrowserPool iniciado | max_sessions={self._max_sessions} "
            f"ttl={self._session_ttl}s"
        )

    def _get_user_lock(self, user_id: int) -> threading.RLock:
        """Retorna lock dedicado ao usuario. Thread-safe."""
        with self._global_lock:
            if user_id not in self._user_locks:
                self._user_locks[user_id] = threading.RLock()
            return self._user_locks[user_id]

    # ------------------------------------------------------------------
    # Acquire / Release
    # ------------------------------------------------------------------

    def acquire(
        self,
        user_id: int,
        task_id: str,
        proxy: Optional[str] = None,
        restore_session: bool = True,
    ) -> BrowserSession:
        """Adquire uma sessao isolada para o usuario.

        Se ja existir uma sessao ativa para este user_id, retorna ela.
        Caso contrario, cria um novo BrowserContext isolado.

        Args:
            user_id: ID do usuario.
            task_id: ID da task atual.
            proxy: URL do proxy (ex: "http://user:pass@host:port"). Opcional.
            restore_session: Se True, restaura cookies salvos do SessionStore.

        Returns:
            BrowserSession com page pronta para uso.

        Raises:
            RuntimeError: Se nao conseguir adquirir slot no semaforo.
        """
        lock = self._get_user_lock(user_id)
        lock.acquire()

        try:
            # Reutilizar sessao existente se valida
            if user_id in self._sessions:
                session = self._sessions[user_id]
                if not session.is_expired:
                    session.task_id = task_id
                    session.touch()
                    logger.debug(f"Reutilizando sessao user={user_id} task={task_id}")
                    return session
                else:
                    # Expirada — fechar e criar nova
                    self._close_session(user_id)

            # Adquirir slot no semaforo (bloqueia se pool cheio)
            acquired = self._semaphore.acquire(timeout=30)
            if not acquired:
                raise RuntimeError(
                    f"BrowserPool cheio ({self._max_sessions} sessoes). "
                    f"Tente novamente em instantes."
                )

            self._ensure_browser()

            # Criar contexto isolado
            session = self._create_session(user_id, task_id, proxy)

            # Restaurar cookies salvos
            if restore_session:
                self._restore_session_cookies(session)

            self._sessions[user_id] = session
            logger.info(
                f"Sessao criada | user={user_id} task={task_id} "
                f"proxy={'sim' if proxy else 'nao'} | "
                f"ativas={len(self._sessions)}/{self._max_sessions}"
            )
            return session

        except Exception:
            lock.release()
            raise

    def release(
        self,
        user_id: int,
        save_session: bool = True,
        close: bool = False,
    ) -> None:
        """Libera a sessao do usuario.

        Args:
            user_id: ID do usuario.
            save_session: Se True, salva cookies no SessionStore.
            close: Se True, fecha o contexto imediatamente.
                   Se False, mantem vivo para reuso (sujeito a TTL).
        """
        lock = self._get_user_lock(user_id)
        try:
            session = self._sessions.get(user_id)
            if session is None:
                return

            if save_session:
                self._save_session_cookies(session)

            if close:
                self._close_session(user_id)
            else:
                session.touch()  # Reset TTL
        finally:
            try:
                lock.release()
            except RuntimeError:
                pass  # Lock nao estava held — ok

    def get_page(self, user_id: int) -> Any:
        """Retorna a Page da sessao ativa do usuario.

        Convenience method para uso nas browser tools.
        Faz touch() automaticamente.

        Raises:
            RuntimeError: Se nao houver sessao ativa.
        """
        session = self._sessions.get(user_id)
        if session is None or session.is_expired:
            raise RuntimeError(
                f"Nenhuma sessao de browser ativa para user_id={user_id}. "
                f"Chame pool.acquire() primeiro."
            )
        session.touch()
        return session.page

    def get_session(self, user_id: int) -> Optional[BrowserSession]:
        """Retorna sessao ativa ou None."""
        session = self._sessions.get(user_id)
        if session and not session.is_expired:
            return session
        return None

    def has_session(self, user_id: int) -> bool:
        """Verifica se usuario tem sessao ativa."""
        session = self._sessions.get(user_id)
        return session is not None and not session.is_expired

    # ------------------------------------------------------------------
    # Criacao de contexto
    # ------------------------------------------------------------------

    def _create_session(
        self,
        user_id: int,
        task_id: str,
        proxy: Optional[str] = None,
    ) -> BrowserSession:
        """Cria novo BrowserContext isolado com stealth."""
        from browser.playwright_client import create_stealth_context

        context, page = create_stealth_context(
            browser=self._browser,
            proxy=proxy,
        )

        return BrowserSession(
            context=context,
            page=page,
            user_id=user_id,
            task_id=task_id,
            proxy=proxy,
        )

    # ------------------------------------------------------------------
    # Session persistence (cookies)
    # ------------------------------------------------------------------

    def _save_session_cookies(self, session: BrowserSession) -> None:
        """Salva cookies da sessao no SessionStore."""
        try:
            from browser.session_store import SessionStore
            store = SessionStore.get_instance()

            cookies = session.context.cookies()
            domain = session.domain or _extract_domain(session.page.url)

            store.save(
                user_id=session.user_id,
                domain=domain,
                cookies=cookies,
            )
            logger.debug(
                f"Cookies salvos | user={session.user_id} "
                f"domain={domain} count={len(cookies)}"
            )
        except Exception as e:
            logger.warning(f"Falha ao salvar cookies user={session.user_id}: {e}")

    def _restore_session_cookies(self, session: BrowserSession) -> None:
        """Restaura cookies salvos para a sessao."""
        try:
            from browser.session_store import SessionStore
            store = SessionStore.get_instance()

            # Restaurar cookies de todos os dominios salvos para este usuario
            cookies = store.load_all(user_id=session.user_id)
            if cookies:
                session.context.add_cookies(cookies)
                logger.debug(
                    f"Cookies restaurados | user={session.user_id} count={len(cookies)}"
                )
        except Exception as e:
            logger.debug(f"Nenhum cookie restaurado user={session.user_id}: {e}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _close_session(self, user_id: int) -> None:
        """Fecha e remove sessao de um usuario."""
        session = self._sessions.pop(user_id, None)
        if session is None:
            return

        try:
            session.page.close()
        except Exception:
            pass
        try:
            session.context.close()
        except Exception:
            pass

        # Liberar slot no semaforo
        self._semaphore.release()

        logger.debug(f"Sessao fechada | user={user_id} age={session.age_seconds:.0f}s")

    def _cleanup_expired(self) -> None:
        """Remove sessoes expiradas. Chamado periodicamente."""
        expired_users = [
            uid for uid, s in self._sessions.items()
            if s.is_expired
        ]
        for uid in expired_users:
            logger.info(
                f"Sessao expirada | user={uid} "
                f"idle={self._sessions[uid].idle_seconds:.0f}s"
            )
            self._save_session_cookies(self._sessions[uid])
            self._close_session(uid)

    def _cleanup_loop(self) -> None:
        """Thread de cleanup periodico."""
        while not self._shutdown_event.is_set():
            self._shutdown_event.wait(CLEANUP_INTERVAL)
            if not self._shutdown_event.is_set():
                try:
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"Erro no cleanup do BrowserPool: {e}")

    def shutdown(self) -> None:
        """Encerra todas as sessoes e o browser."""
        logger.info("BrowserPool shutdown iniciado...")
        self._shutdown_event.set()

        # Fechar todas as sessoes
        for uid in list(self._sessions.keys()):
            try:
                self._save_session_cookies(self._sessions[uid])
            except Exception:
                pass
            self._close_session(uid)

        # Fechar browser
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception as e:
                logger.warning(f"Erro ao fechar browser: {e}")
            self._browser = None

        # Encerrar Playwright
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception as e:
                logger.warning(f"Erro ao encerrar Playwright: {e}")
            self._pw = None

        self._started = False
        logger.info("BrowserPool shutdown completo")

    def _atexit_cleanup(self) -> None:
        """Handler de atexit — garante cleanup em caso de crash."""
        if self._started:
            try:
                self.shutdown()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Metricas
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Retorna metricas do pool."""
        sessions_info = []
        for uid, s in self._sessions.items():
            sessions_info.append({
                "user_id": uid,
                "task_id": s.task_id,
                "age_seconds": round(s.age_seconds),
                "idle_seconds": round(s.idle_seconds),
                "domain": s.domain,
                "proxy": bool(s.proxy),
            })

        return {
            "active_sessions": len(self._sessions),
            "max_sessions": self._max_sessions,
            "session_ttl": self._session_ttl,
            "browser_running": self._browser is not None,
            "sessions": sessions_info,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_domain(url: str) -> str:
    """Extrai dominio de uma URL."""
    try:
        return urlparse(url).netloc or "unknown"
    except Exception:
        return "unknown"
