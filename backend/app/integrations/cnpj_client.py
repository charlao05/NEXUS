"""
Client de consulta CNPJ — detecção de status MEI.

Suporta múltiplos provedores (abstração por enum):
- OpenCNPJ (gratuito, dados abertos, sem chave)
- CNPJá (plano open + comercial)
- CNPJ.ws (comercial)
- BrasilAPI (gratuito, comunidade)

Todos retornam MEIProfile via parser tolerante.
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Optional

from .http_base import ExternalAPIClient, ExternalAPIClientError, ExternalAPIError
from .domain.mei_models import MEIProfile

logger = logging.getLogger(__name__)


class CNPJProvider(str, Enum):
    """Provedores suportados para consulta de CNPJ."""
    OPENCNPJ = "opencnpj"
    CNPJA = "cnpja"
    CNPJWS = "cnpjws"
    BRASILAPI = "brasilapi"


# ── Configurações por provedor ───────────────────────────────────────────────

_PROVIDER_CONFIG = {
    CNPJProvider.OPENCNPJ: {
        "base_url": "https://opencnpj.org",
        "path_template": "/v1/cnpj/{cnpj}",
        "needs_key": False,
    },
    CNPJProvider.CNPJA: {
        "base_url": "https://open.cnpja.com",
        "path_template": "/office/{cnpj}",
        "needs_key": False,  # open tier não precisa; comercial sim
    },
    CNPJProvider.CNPJWS: {
        "base_url": "https://comercial.cnpj.ws",
        "path_template": "/cnpj/{cnpj}",
        "needs_key": True,
        "key_env": "CNPJWS_API_KEY",
        "key_header": "x-api-key",
    },
    CNPJProvider.BRASILAPI: {
        "base_url": "https://brasilapi.com.br",
        "path_template": "/api/cnpj/v1/{cnpj}",
        "needs_key": False,
    },
}


class CNPJClient(ExternalAPIClient):
    """
    Client unificado para consulta CNPJ / status MEI.

    Exemplo:
        async with CNPJClient() as client:
            profile = await client.consultar_mei("12345678000199")
    """

    SERVICE_NAME = "cnpj"

    def __init__(
        self,
        provider: CNPJProvider = CNPJProvider.BRASILAPI,
        api_key: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.provider = provider
        config = _PROVIDER_CONFIG[provider]

        headers = {}
        if config.get("needs_key"):
            key = api_key or os.getenv(config.get("key_env", ""), "")
            if key:
                headers[config["key_header"]] = key

        super().__init__(
            base_url=config["base_url"],
            timeout=timeout,
            headers=headers,
        )

        self._path_template = config["path_template"]

    async def get_cnpj_raw(self, cnpj: str) -> dict:
        """
        Busca dados brutos de um CNPJ na API do provedor.

        Args:
            cnpj: CNPJ (com ou sem máscara)

        Returns:
            dict com payload cru da API
        """
        cnpj_limpo = self.validate_cnpj(cnpj)
        path = self._path_template.format(cnpj=cnpj_limpo)

        logger.info(
            "[%s] Consultando CNPJ %s via %s",
            self.SERVICE_NAME,
            self.mask_cnpj(cnpj_limpo),
            self.provider.value,
        )

        data = await self._request("GET", path)

        if not isinstance(data, dict):
            raise ExternalAPIError(
                f"Resposta inesperada do provedor {self.provider.value}",
                service=self.SERVICE_NAME,
                details=str(data)[:200],
            )

        return data

    async def consultar_mei(self, cnpj: str) -> MEIProfile:
        """
        Consulta CNPJ e retorna MEIProfile estruturado.

        Args:
            cnpj: CNPJ do MEI

        Returns:
            MEIProfile com dados do cadastro e flag is_mei
        """
        raw = await self.get_cnpj_raw(cnpj)
        profile = MEIProfile.from_cnpj_payload(raw, fonte=self.provider.value)

        logger.info(
            "[%s] CNPJ %s → MEI=%s, Situação=%s",
            self.SERVICE_NAME,
            self.mask_cnpj(profile.cnpj),
            profile.is_mei,
            profile.situacao_cadastral.value,
        )

        return profile


# ── Factory com fallback ─────────────────────────────────────────────────────

async def consultar_cnpj_com_fallback(
    cnpj: str,
    providers: Optional[list[CNPJProvider]] = None,
) -> MEIProfile:
    """
    Tenta consultar CNPJ em múltiplos provedores com fallback.

    Ordem padrão: BrasilAPI → OpenCNPJ → CNPJá
    """
    if providers is None:
        providers = [CNPJProvider.BRASILAPI, CNPJProvider.OPENCNPJ, CNPJProvider.CNPJA]

    last_error: Optional[Exception] = None

    for provider in providers:
        try:
            async with CNPJClient(provider=provider) as client:
                return await client.consultar_mei(cnpj)
        except ExternalAPIClientError:
            raise  # 4xx = não existe ou input errado, não faz sentido tentar outro
        except Exception as e:
            logger.warning(
                "Provedor %s falhou para CNPJ %s: %s",
                provider.value,
                ExternalAPIClient.mask_cnpj(cnpj),
                e,
            )
            last_error = e
            continue

    raise ExternalAPIError(
        f"Todos os provedores falharam para CNPJ {ExternalAPIClient.mask_cnpj(cnpj)}",
        service="cnpj-fallback",
        details=str(last_error),
    )
