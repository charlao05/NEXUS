"""
Client — Consulta CND (Certidão Negativa de Débitos).

Fontes possíveis:
- SERPRO Conecta (API oficial, acesso comercial)
- APIs de terceiros (Infosimples, DirectD, etc.)

Env vars:
- CND_PROVIDER: "serpro" | "infosimples" | "mock"
- CND_API_KEY: Chave da API escolhida
- CND_BASE_URL: URL base (se customizado)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from .http_base import ExternalAPIClient, ExternalAPIError
from .domain.fiscal_models import CNDStatus, TipoCertidao

logger = logging.getLogger(__name__)


class CNDClient(ExternalAPIClient):
    """
    Client para consulta de CND (Certidão Negativa de Débitos).

    O provedor é configurável via env. Se não configurado,
    opera em modo "mock" retornando status indisponível.
    """

    SERVICE_NAME = "cnd"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: Optional[str] = None,
        timeout: float = 20.0,
    ):
        self.provider = provider or os.getenv("CND_PROVIDER", "mock")
        key = api_key or os.getenv("CND_API_KEY", "")

        # URLs por provedor
        urls = {
            "serpro": "https://apigateway.conectagov.estaleiro.serpro.gov.br",
            "infosimples": "https://api.infosimples.com",
            "mock": "http://localhost",
        }
        url = base_url or urls.get(self.provider, "http://localhost")

        headers = {}
        if key and self.provider == "serpro":
            headers["Authorization"] = f"Bearer {key}"
        elif key and self.provider == "infosimples":
            headers["x-api-key"] = key

        super().__init__(base_url=url, timeout=timeout, headers=headers)

    async def consultar_cnd(self, cnpj: str) -> CNDStatus:
        """
        Consulta CND para um CNPJ.

        Returns:
            CNDStatus com tipo_certidao e indicador de aptidão
        """
        cnpj_limpo = self.validate_cnpj(cnpj)

        logger.info(
            "[%s] Consultando CND para %s via %s",
            self.SERVICE_NAME,
            self.mask_cnpj(cnpj_limpo),
            self.provider,
        )

        if self.provider == "mock":
            return self._mock_cnd(cnpj_limpo)

        if self.provider == "serpro":
            return await self._consultar_serpro(cnpj_limpo)

        if self.provider == "infosimples":
            return await self._consultar_infosimples(cnpj_limpo)

        raise ExternalAPIError(
            f"Provedor de CND não suportado: {self.provider}",
            service=self.SERVICE_NAME,
        )

    async def _consultar_serpro(self, cnpj: str) -> CNDStatus:
        """Consulta via API Conecta/SERPRO."""
        path = f"/api-cnd/v1/certidao/{cnpj}"
        data = await self._request("GET", path)

        if not isinstance(data, dict):
            raise ExternalAPIError(
                "Resposta inesperada da API SERPRO CND",
                service=self.SERVICE_NAME,
            )

        return CNDStatus.from_api_payload(cnpj, data, fonte="serpro")

    async def _consultar_infosimples(self, cnpj: str) -> CNDStatus:
        """Consulta via Infosimples."""
        path = "/api/v2/consultas/receita-federal/cnd"
        data = await self._request(
            "GET",
            path,
            params={"cnpj": cnpj},
        )

        if not isinstance(data, dict):
            raise ExternalAPIError(
                "Resposta inesperada da API Infosimples CND",
                service=self.SERVICE_NAME,
            )

        # Infosimples retorna no campo "data"
        result = data.get("data", [{}])
        payload = result[0] if isinstance(result, list) and result else {}

        return CNDStatus.from_api_payload(cnpj, payload, fonte="infosimples")

    @staticmethod
    def _mock_cnd(cnpj: str) -> CNDStatus:
        """Retorna CND indisponível (sem integração configurada)."""
        return CNDStatus(
            cnpj=cnpj,
            tipo_certidao=TipoCertidao.INDISPONIVEL,
            apto_contratar_governo=False,
            observacao=(
                "Consulta de CND não configurada. "
                "Configure CND_PROVIDER e CND_API_KEY no .env "
                "para habilitar consulta real."
            ),
            fonte="mock",
        )
