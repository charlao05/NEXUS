"""
Client — API de Transparência Municipal: Serra/ES.

A Prefeitura da Serra disponibiliza Portal da Transparência
com API de integração e extração de dados.
Ref: http://www4.serra.es.gov.br/site/pagina/portal-transparencia
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .http_base import ExternalAPIClient
from .domain.nfse_transparencia_models import PagamentoGoverno

logger = logging.getLogger(__name__)


class TransparenciaSerraClient(ExternalAPIClient):
    """
    Client para API de Transparência — Prefeitura da Serra/ES.

    NOTA: A URL base e endpoints devem ser confirmados na
    documentação oficial da prefeitura. Os paths abaixo são
    baseados no padrão comum de portais de transparência.
    """

    SERVICE_NAME = "transparencia-serra"

    def __init__(self, base_url: str = "http://www4.serra.es.gov.br", timeout: float = 15.0):
        super().__init__(base_url=base_url, timeout=timeout)

    async def buscar_despesas_fornecedor(
        self,
        cnpj: str,
        ano: int,
        pagina: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Busca despesas pagas a um fornecedor (CNPJ) em Serra.
        """
        cnpj_limpo = self.validate_cnpj(cnpj)

        params: Dict[str, Any] = {
            "cnpj": cnpj_limpo,
            "ano": ano,
            "pagina": pagina,
        }

        logger.info(
            "[%s] Buscando despesas para %s em Serra (ano=%d)",
            self.SERVICE_NAME,
            self.mask_cnpj(cnpj_limpo),
            ano,
        )

        # Endpoint placeholder — ajustar conforme doc real
        data = await self._request("GET", "/api/despesas/fornecedor", params=params)

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("registros", []))
        return []

    def parse_pagamentos(
        self,
        registros: List[Dict[str, Any]],
        cnpj: str,
    ) -> List[PagamentoGoverno]:
        """Converte registros da API em PagamentoGoverno padronizado."""
        resultado = []
        for reg in registros:
            resultado.append(PagamentoGoverno(
                cnpj_favorecido=self.clean_cnpj(cnpj),
                nome_favorecido=reg.get("fornecedor", reg.get("nome", "")),
                orgao=reg.get("orgao", "Prefeitura da Serra"),
                valor=float(reg.get("valor", reg.get("valorPago", 0))),
                ano=reg.get("ano", reg.get("exercicio")),
                fonte="transparencia_serra",
            ))
        return resultado
