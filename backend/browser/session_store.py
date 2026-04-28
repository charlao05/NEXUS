"""
SessionStore — Persistencia de cookies/storage por usuario+dominio.
=====================================================================
Salva e restaura cookies de browser entre tasks, para que logins
manuais (gov.br, bancos) feitos pelo usuario nao se percam.

Backends:
- Redis (producao): chave `nexus:browser:session:{user_id}:{domain}` com TTL
- In-memory (fallback): dict thread-safe quando Redis nao disponivel

Cookies sao serializados em JSON. TTL padrao = 7 dias (renovavel).
Cookies marcados como `httpOnly` ou `secure` sao preservados.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

SESSION_TTL_SECONDS = int(os.getenv("BROWSER_SESSION_TTL", str(7 * 24 * 3600)))  # 7 dias
KEY_PREFIX = "nexus:browser:session"


# ---------------------------------------------------------------------------
# SessionStore
# ---------------------------------------------------------------------------

class SessionStore:
    """Armazena/recupera cookies por user_id+domain.

    Thread-safe. Singleton via get_instance().
    """

    _instance: Optional[SessionStore] = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._memory: dict[str, dict[str, Any]] = {}
        self._memory_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> SessionStore:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset para testes."""
        with cls._instance_lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Backend Redis
    # ------------------------------------------------------------------

    def _get_redis(self):
        """Tenta obter cliente Redis; retorna None se indisponivel."""
        try:
            from app.api.redis_client import get_redis
            return get_redis()
        except Exception:
            return None

    def _build_key(self, user_id: int, domain: str) -> str:
        domain_safe = domain.replace(":", "_").lower() if domain else "default"
        return f"{KEY_PREFIX}:{user_id}:{domain_safe}"

    def _scan_user_keys(self, user_id: int) -> list[str]:
        """Lista todas as chaves de um usuario (Redis SCAN ou memoria)."""
        prefix = f"{KEY_PREFIX}:{user_id}:"
        redis = self._get_redis()
        if redis is not None:
            try:
                return [
                    k for k in redis.scan_iter(match=f"{prefix}*", count=100)
                ]
            except Exception as e:
                logger.warning(f"SessionStore scan falhou: {e}")

        with self._memory_lock:
            return [k for k in self._memory.keys() if k.startswith(prefix)]

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def save(
        self,
        user_id: int,
        domain: str,
        cookies: list[dict[str, Any]],
        ttl_seconds: int = SESSION_TTL_SECONDS,
    ) -> None:
        """Salva cookies para o par user_id+domain.

        Args:
            user_id: ID do usuario.
            domain: Dominio (ex: "www.gov.br").
            cookies: Lista de cookies no formato Playwright.
            ttl_seconds: TTL em segundos (padrao 7 dias).
        """
        if not cookies:
            return

        # Filtrar cookies relevantes para o dominio (mantem todos httpOnly)
        filtered = self._filter_cookies(cookies, domain)
        if not filtered:
            return

        key = self._build_key(user_id, domain)
        payload = {
            "cookies": filtered,
            "saved_at": time.time(),
            "domain": domain,
        }

        redis = self._get_redis()
        if redis is not None:
            try:
                redis.setex(key, ttl_seconds, json.dumps(payload))
                logger.debug(
                    f"SessionStore.save (redis) | user={user_id} "
                    f"domain={domain} cookies={len(filtered)}"
                )
                return
            except Exception as e:
                logger.warning(f"SessionStore Redis save falhou: {e} — fallback memoria")

        with self._memory_lock:
            payload["expires_at"] = time.time() + ttl_seconds
            self._memory[key] = payload
            logger.debug(
                f"SessionStore.save (memoria) | user={user_id} "
                f"domain={domain} cookies={len(filtered)}"
            )

    def load(self, user_id: int, domain: str) -> list[dict[str, Any]]:
        """Carrega cookies salvos para o par user_id+domain.

        Returns:
            Lista de cookies ou [] se nao houver.
        """
        key = self._build_key(user_id, domain)

        redis = self._get_redis()
        if redis is not None:
            try:
                raw = redis.get(key)
                if raw:
                    payload = json.loads(raw)
                    return payload.get("cookies", [])
            except Exception as e:
                logger.warning(f"SessionStore Redis load falhou: {e}")

        with self._memory_lock:
            payload = self._memory.get(key)
            if payload is None:
                return []
            if payload.get("expires_at", 0) < time.time():
                self._memory.pop(key, None)
                return []
            return payload.get("cookies", [])

    def load_all(self, user_id: int) -> list[dict[str, Any]]:
        """Carrega TODOS os cookies salvos para o usuario (todos dominios).

        Util ao iniciar uma sessao do pool, para restaurar tudo de uma vez.
        """
        all_cookies: list[dict[str, Any]] = []
        keys = self._scan_user_keys(user_id)

        redis = self._get_redis()
        for key in keys:
            try:
                if redis is not None:
                    raw = redis.get(key)
                    if raw:
                        payload = json.loads(raw)
                        all_cookies.extend(payload.get("cookies", []))
                else:
                    with self._memory_lock:
                        payload = self._memory.get(key)
                        if payload and payload.get("expires_at", 0) >= time.time():
                            all_cookies.extend(payload.get("cookies", []))
            except Exception as e:
                logger.debug(f"SessionStore load_all falhou para {key}: {e}")

        return all_cookies

    def clear(self, user_id: int, domain: Optional[str] = None) -> int:
        """Remove cookies salvos.

        Args:
            user_id: ID do usuario.
            domain: Se fornecido, limpa apenas este dominio. Senao, limpa tudo.

        Returns:
            Numero de chaves removidas.
        """
        if domain is not None:
            keys = [self._build_key(user_id, domain)]
        else:
            keys = self._scan_user_keys(user_id)

        if not keys:
            return 0

        removed = 0
        redis = self._get_redis()
        if redis is not None:
            try:
                removed = redis.delete(*keys)
                logger.info(f"SessionStore.clear (redis) | user={user_id} removidas={removed}")
                return removed
            except Exception as e:
                logger.warning(f"SessionStore Redis clear falhou: {e}")

        with self._memory_lock:
            for k in keys:
                if self._memory.pop(k, None) is not None:
                    removed += 1
            logger.info(f"SessionStore.clear (memoria) | user={user_id} removidas={removed}")

        return removed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_cookies(cookies: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
        """Filtra cookies relevantes para o dominio.

        Aceita cookies do dominio principal + subdominios.
        Remove cookies sem nome ou valor.
        """
        if not domain:
            return [c for c in cookies if c.get("name") and c.get("value")]

        # Normalizar dominio (remove port se houver)
        domain_root = domain.split(":")[0].lower()

        result = []
        for c in cookies:
            cname = c.get("name", "")
            cvalue = c.get("value", "")
            cdomain = (c.get("domain", "") or "").lstrip(".").lower()

            if not cname or cvalue is None:
                continue

            # Aceita: cookie do mesmo dominio raiz OU subdominio
            if cdomain and (
                cdomain == domain_root
                or domain_root.endswith(cdomain)
                or cdomain.endswith(domain_root.split(".", 1)[-1] if "." in domain_root else domain_root)
            ):
                result.append(c)
            elif not cdomain:
                # Cookies sem domain explicito (sessao) — manter
                result.append(c)

        return result
