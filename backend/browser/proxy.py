"""
ProxyPool — Configuracao e rotacao de proxies HTTP/SOCKS.
==========================================================
Le proxies do env var PROXY_URLS (separados por virgula) e
distribui via round-robin entre as sessoes do BrowserPool.

Formato suportado (Playwright):
    http://user:pass@host:port
    https://host:port
    socks5://user:pass@host:port

Sem PROXY_URLS configurada, o pool funciona sem proxy (sai do IP do Render).
"""
from __future__ import annotations

import logging
import os
import threading
from itertools import cycle
from typing import Iterator, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _parse_proxy_list(env_value: str) -> list[str]:
    """Parse PROXY_URLS=url1,url2,url3 -> [url1, url2, url3]."""
    if not env_value:
        return []
    return [u.strip() for u in env_value.split(",") if u.strip()]


def _to_playwright_proxy(proxy_url: str) -> Optional[dict[str, str]]:
    """Converte URL de proxy para o formato dict que o Playwright espera.

    Retorna None se URL invalida.
    """
    try:
        parsed = urlparse(proxy_url)
        if not parsed.hostname:
            return None

        scheme = parsed.scheme or "http"
        port_part = f":{parsed.port}" if parsed.port else ""
        server = f"{scheme}://{parsed.hostname}{port_part}"

        result: dict[str, str] = {"server": server}
        if parsed.username:
            result["username"] = parsed.username
        if parsed.password:
            result["password"] = parsed.password
        return result
    except Exception as e:
        logger.warning(f"Proxy URL invalida ignorada: {proxy_url[:30]}... ({e})")
        return None


class ProxyPool:
    """Pool de proxies com round-robin thread-safe."""

    _instance: Optional[ProxyPool] = None
    _instance_lock = threading.Lock()

    def __init__(self):
        env_value = os.getenv("PROXY_URLS", "")
        self._proxy_urls: list[str] = _parse_proxy_list(env_value)
        self._cycle: Iterator[str] = cycle(self._proxy_urls) if self._proxy_urls else iter([])
        self._lock = threading.Lock()

        if self._proxy_urls:
            logger.info(
                f"ProxyPool inicializado | proxies={len(self._proxy_urls)} "
                f"(rotacao round-robin)"
            )
        else:
            logger.info("ProxyPool sem proxies configurados — saindo direto do IP do Render")

    @classmethod
    def get_instance(cls) -> ProxyPool:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._instance_lock:
            cls._instance = None

    def has_proxies(self) -> bool:
        return bool(self._proxy_urls)

    def next_proxy_url(self) -> Optional[str]:
        """Retorna proxima URL de proxy (string). Round-robin."""
        if not self._proxy_urls:
            return None
        with self._lock:
            return next(self._cycle)

    def next_playwright_config(self) -> Optional[dict[str, str]]:
        """Retorna proximo proxy no formato Playwright. Round-robin."""
        url = self.next_proxy_url()
        if url is None:
            return None
        return _to_playwright_proxy(url)

    def stats(self) -> dict:
        return {
            "proxy_count": len(self._proxy_urls),
            "configured": bool(self._proxy_urls),
        }
