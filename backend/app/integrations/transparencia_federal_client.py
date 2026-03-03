"""
Client — Portal da Transparência (federal).

API oficial: https://api.portaldatransparencia.gov.br
Documentação: https://portaldatransparencia.gov.br/api-de-dados

Requer chave de API (gratuita, cadastro no portal).
Env var: TRANSPARENCIA_API_KEY
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from .http_base import ExternalAPIClient, ExternalAPIError
from .domain.nfse_transparencia_models import PagamentoGoverno, ResumoTransparencia

logger = logging.getLogger(__name__)


class TransparenciaFederalClient(ExternalAPIClient):
    """
    Client para API do Portal da Transparência do Governo Federal.

    Endpoints suportados:
    - Pagamentos por favorecido (CNPJ)
    - Contratos por fornecedor
    """

    SERVICE_NAME = "transparencia-federal"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 20.0,
    ):
        key = api_key or os.getenv("TRANSPARENCIA_API_KEY", "")

        headers = {}
        if key:
            headers["chave-api-dados"] = key

        super().__init__(
            base_url="https://api.portaldatransparencia.gov.br",
            timeout=timeout,
            headers=headers,
        )

    async def buscar_pagamentos(
        self,
        cnpj: str,
        ano: Optional[int] = None,
        pagina: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Busca pagamentos recebidos por um CNPJ (favorecido).

        Retorna lista de registros crus da API.
        """
        cnpj_limpo = self.validate_cnpj(cnpj)

        params: Dict[str, Any] = {
            "codigoFavorecido": cnpj_limpo,
            "pagina": pagina,
        }
        if ano:
            params["ano"] = ano

        logger.info(
            "[%s] Buscando pagamentos para %s (ano=%s, pag=%d)",
            self.SERVICE_NAME,
            self.mask_cnpj(cnpj_limpo),
            ano or "todos",
            pagina,
        )

        data = await self._request("GET", "/api-de-dados/despesas/por-favorecido", params=params)

        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return []

    async def buscar_contratos(
        self,
        cnpj: str,
        pagina: int = 1,
    ) -> List[Dict[str, Any]]:
        """Busca contratos do governo federal com um CNPJ fornecedor."""
        cnpj_limpo = self.validate_cnpj(cnpj)

        params: Dict[str, Any] = {
            "codigoOrgao": "",  # qualquer
            "cnpjFornecedor": cnpj_limpo,
            "pagina": pagina,
        }

        data = await self._request("GET", "/api-de-dados/contratos", params=params)

        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return []

    async def resumo_pagamentos(
        self,
        cnpj: str,
        ano: Optional[int] = None,
        max_paginas: int = 5,
    ) -> ResumoTransparencia:
        """
        Busca todas as páginas de pagamentos e monta ResumoTransparencia.

        Limita a max_paginas para evitar uso excessivo de quota.
        """
        cnpj_limpo = self.validate_cnpj(cnpj)
        todos_pagamentos: List[PagamentoGoverno] = []
        orgaos: set = set()

        for pagina in range(1, max_paginas + 1):
            try:
                registros = await self.buscar_pagamentos(cnpj_limpo, ano=ano, pagina=pagina)
            except ExternalAPIError:
                break

            if not registros:
                break

            for reg in registros:
                valor = float(reg.get("valor", 0))
                orgao = reg.get("orgaoSuperior", {}).get("nome", "") if isinstance(reg.get("orgaoSuperior"), dict) else ""
                pgto = PagamentoGoverno(
                    cnpj_favorecido=cnpj_limpo,
                    nome_favorecido=reg.get("favorecido", {}).get("nome", "") if isinstance(reg.get("favorecido"), dict) else "",
                    orgao=orgao,
                    valor=valor,
                    ano=reg.get("ano"),
                    mes=reg.get("mes"),
                    fonte="transparencia_federal",
                )
                todos_pagamentos.append(pgto)
                if orgao:
                    orgaos.add(orgao)

        valor_total = sum(p.valor for p in todos_pagamentos)

        return ResumoTransparencia(
            cnpj=cnpj_limpo,
            total_pagamentos=len(todos_pagamentos),
            valor_total=valor_total,
            pagamentos_federais=len(todos_pagamentos),
            valor_federal=valor_total,
            pagamentos=todos_pagamentos[:100],  # Limita lista detalhada
            orgaos_pagadores=sorted(orgaos),
        )
