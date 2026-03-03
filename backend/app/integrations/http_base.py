"""
Client HTTP base assíncrono para todas as integrações externas.

Padroniza:
- Timeouts configuráveis
- Retry automático em 5xx e erros de rede
- Log estruturado (CNPJ mascarado)
- Tratamento 4xx / 5xx diferenciado
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


# ── Exceções ─────────────────────────────────────────────────────────────────

class ExternalAPIError(Exception):
    """Erro genérico em chamadas de APIs externas."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        details: Any = None,
        service: str = "unknown",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.details = details
        self.service = service


class ExternalAPIClientError(ExternalAPIError):
    """Erros 4xx — problema de entrada ou permissão."""


class ExternalAPIServerError(ExternalAPIError):
    """Erros 5xx — falha no servidor remoto."""


class ExternalAPITimeoutError(ExternalAPIError):
    """Timeout ao chamar API externa."""


# ── Client base ──────────────────────────────────────────────────────────────

class ExternalAPIClient:
    """
    Base para todos os clients de APIs externas.

    Uso:
        class MeuClient(ExternalAPIClient):
            async def buscar(self, id: str):
                return await self._request("GET", f"/recurso/{id}")
    """

    SERVICE_NAME: str = "external"  # Sobrescreva nas subclasses

    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 2,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.default_headers = headers or {}

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.default_headers,
            follow_redirects=True,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def mask_cnpj(cnpj: str) -> str:
        """Mascara CNPJ para log: 12345678000199 → 12.345.***/**99."""
        digits = "".join(filter(str.isdigit, cnpj))
        if len(digits) >= 10:
            return f"{digits[:2]}.{digits[2:5]}.***/{digits[-4:-2]}**"
        return "***masked***"

    @staticmethod
    def clean_cnpj(cnpj: str) -> str:
        """Remove máscara de CNPJ, retornando apenas dígitos."""
        return "".join(filter(str.isdigit, cnpj))

    @staticmethod
    def validate_cnpj(cnpj: str) -> str:
        """Limpa e valida CNPJ (14 dígitos). Levanta ValueError se inválido."""
        digits = "".join(filter(str.isdigit, cnpj))
        if len(digits) != 14:
            raise ValueError(f"CNPJ inválido (esperado 14 dígitos, recebido {len(digits)})")
        return digits

    # ── Request principal ────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        expected_status: int = 200,
        max_retries: Optional[int] = None,
    ) -> Any:
        """
        Executa request HTTP com retry em 5xx / erros de rede.

        Retorna JSON parsed (dict/list) ou texto se não for JSON.
        """
        retries = max_retries if max_retries is not None else self.max_retries
        merged_headers = {**self.default_headers, **(headers or {})}

        last_exc: Optional[ExternalAPIError] = None

        for attempt in range(retries + 1):
            try:
                resp = await self._client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json_body,
                    data=data,
                    headers=merged_headers,
                )

                # ── Sucesso ──────────────────────────────────────────────────
                if resp.status_code == expected_status:
                    try:
                        return resp.json()
                    except (ValueError, Exception):
                        return resp.text

                # ── Extrair corpo do erro ────────────────────────────────────
                error_body: Any = None
                try:
                    error_body = resp.json()
                except (ValueError, Exception):
                    error_body = resp.text[:500] if resp.text else None

                # ── 4xx — erro de cliente (não retryável) ────────────────────
                if 400 <= resp.status_code < 500:
                    logger.warning(
                        "[%s] Erro %d em %s %s",
                        self.SERVICE_NAME,
                        resp.status_code,
                        method,
                        path,
                        extra={"status": resp.status_code, "body": error_body},
                    )
                    raise ExternalAPIClientError(
                        f"[{self.SERVICE_NAME}] Erro {resp.status_code} em {method} {path}",
                        status_code=resp.status_code,
                        details=error_body,
                        service=self.SERVICE_NAME,
                    )

                # ── 5xx — erro de servidor (retryável) ──────────────────────
                if resp.status_code >= 500:
                    logger.error(
                        "[%s] Erro %d em %s %s (tentativa %d/%d)",
                        self.SERVICE_NAME,
                        resp.status_code,
                        method,
                        path,
                        attempt + 1,
                        retries + 1,
                    )
                    last_exc = ExternalAPIServerError(
                        f"[{self.SERVICE_NAME}] Erro {resp.status_code}",
                        status_code=resp.status_code,
                        details=error_body,
                        service=self.SERVICE_NAME,
                    )
                    continue

                # ── Outros status inesperados ────────────────────────────────
                logger.warning(
                    "[%s] Status inesperado %d (esperado %d) em %s %s",
                    self.SERVICE_NAME,
                    resp.status_code,
                    expected_status,
                    method,
                    path,
                )
                raise ExternalAPIError(
                    f"[{self.SERVICE_NAME}] Status inesperado {resp.status_code}",
                    status_code=resp.status_code,
                    details=error_body,
                    service=self.SERVICE_NAME,
                )

            except (httpx.TimeoutException,) as exc:
                logger.warning(
                    "[%s] Timeout em %s %s (tentativa %d/%d): %s",
                    self.SERVICE_NAME,
                    method,
                    path,
                    attempt + 1,
                    retries + 1,
                    exc,
                )
                last_exc = ExternalAPITimeoutError(
                    f"[{self.SERVICE_NAME}] Timeout em {method} {path}",
                    service=self.SERVICE_NAME,
                    details=str(exc),
                )
                continue

            except (httpx.NetworkError,) as exc:
                logger.warning(
                    "[%s] Erro de rede em %s %s (tentativa %d/%d): %s",
                    self.SERVICE_NAME,
                    method,
                    path,
                    attempt + 1,
                    retries + 1,
                    exc,
                )
                last_exc = ExternalAPIError(
                    f"[{self.SERVICE_NAME}] Erro de rede: {exc}",
                    service=self.SERVICE_NAME,
                    details=str(exc),
                )
                continue

        # Todas as tentativas falharam
        raise last_exc or ExternalAPIError(
            f"[{self.SERVICE_NAME}] Falha após {retries + 1} tentativas",
            service=self.SERVICE_NAME,
        )

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Fechar conexão httpx."""
        await self._client.aclose()

    async def __aenter__(self) -> "ExternalAPIClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
