"""
Client — Dívida Ativa da União (PGFN).

Fontes:
- SERPRO Conecta (API Consulta Dívida Ativa da União)
- Dados abertos PGFN (CSVs trimestrais — análise em massa)

Env vars:
- DIVIDA_ATIVA_PROVIDER: "serpro" | "mock"
- DIVIDA_ATIVA_API_KEY: Chave da API
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from .http_base import ExternalAPIClient, ExternalAPIError
from .domain.fiscal_models import (
    DividaAtivaStatus,
    InscricaoDividaAtiva,
    SituacaoDividaAtiva,
)

logger = logging.getLogger(__name__)


class DividaAtivaClient(ExternalAPIClient):
    """
    Client para consulta de Dívida Ativa da União (PGFN).
    """

    SERVICE_NAME = "divida-ativa"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: Optional[str] = None,
        timeout: float = 20.0,
    ):
        self.provider = provider or os.getenv("DIVIDA_ATIVA_PROVIDER", "mock")
        key = api_key or os.getenv("DIVIDA_ATIVA_API_KEY", "")

        urls = {
            "serpro": "https://apigateway.conectagov.estaleiro.serpro.gov.br",
            "mock": "http://localhost",
        }
        url = base_url or urls.get(self.provider, "http://localhost")

        headers = {}
        if key and self.provider == "serpro":
            headers["Authorization"] = f"Bearer {key}"

        super().__init__(base_url=url, timeout=timeout, headers=headers)

    async def consultar(self, cnpj: str) -> DividaAtivaStatus:
        """
        Consulta dívida ativa para um CNPJ.

        Returns:
            DividaAtivaStatus com inscrições e valores
        """
        cnpj_limpo = self.validate_cnpj(cnpj)

        logger.info(
            "[%s] Consultando dívida ativa para %s via %s",
            self.SERVICE_NAME,
            self.mask_cnpj(cnpj_limpo),
            self.provider,
        )

        if self.provider == "mock":
            return self._mock_response(cnpj_limpo)

        if self.provider == "serpro":
            return await self._consultar_serpro(cnpj_limpo)

        raise ExternalAPIError(
            f"Provedor de Dívida Ativa não suportado: {self.provider}",
            service=self.SERVICE_NAME,
        )

    async def _consultar_serpro(self, cnpj: str) -> DividaAtivaStatus:
        """Consulta via API Conecta/SERPRO."""
        path = f"/api-pgfn-divida-ativa/v1/divida/{cnpj}"
        data = await self._request("GET", path)

        if not isinstance(data, dict):
            raise ExternalAPIError(
                "Resposta inesperada da API SERPRO Dívida Ativa",
                service=self.SERVICE_NAME,
            )

        inscricoes_raw = data.get("inscricoes", [])
        inscricoes: List[InscricaoDividaAtiva] = []

        for insc in inscricoes_raw:
            sit_raw = str(insc.get("situacao", "")).lower()
            sit_map = {
                "em cobrança": SituacaoDividaAtiva.EM_COBRANCA,
                "em cobranca": SituacaoDividaAtiva.EM_COBRANCA,
                "parcelada": SituacaoDividaAtiva.PARCELADA,
                "ajuizada": SituacaoDividaAtiva.AJUIZADA,
                "suspensa": SituacaoDividaAtiva.SUSPENSA,
            }
            inscricoes.append(InscricaoDividaAtiva(
                numero_inscricao=str(insc.get("numero", "")),
                valor_consolidado=float(insc.get("valor", 0)),
                situacao=sit_map.get(sit_raw, SituacaoDividaAtiva.DESCONHECIDA),
                tipo_devedor=insc.get("tipo_devedor"),
                indicador_ajuizado=insc.get("ajuizado", False),
            ))

        valor_total = sum(i.valor_consolidado for i in inscricoes)

        return DividaAtivaStatus(
            cnpj=cnpj,
            tem_divida=len(inscricoes) > 0,
            total_dividas=len(inscricoes),
            valor_total=valor_total,
            inscricoes=inscricoes,
            fonte="serpro",
        )

    @staticmethod
    def _mock_response(cnpj: str) -> DividaAtivaStatus:
        """Resposta mock (integração não configurada)."""
        return DividaAtivaStatus(
            cnpj=cnpj,
            tem_divida=False,
            total_dividas=0,
            valor_total=0.0,
            inscricoes=[],
            fonte="mock",
        )
