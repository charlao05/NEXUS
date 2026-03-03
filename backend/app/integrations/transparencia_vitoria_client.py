"""
Client — API de Transparência Municipal: Vitória/ES.

API Web: https://wstransparencia.vitoria.es.gov.br
Endpoints REST/JSON públicos para despesas, receitas, etc.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .http_base import ExternalAPIClient, ExternalAPIError
from .domain.nfse_transparencia_models import PagamentoGoverno

logger = logging.getLogger(__name__)


class TransparenciaVitoriaClient(ExternalAPIClient):
    """
    Client para API Web de Transparência — Prefeitura de Vitória/ES.

    Documentação: https://wstransparencia.vitoria.es.gov.br
    Formato: REST + JSON
    """

    SERVICE_NAME = "transparencia-vitoria"

    def __init__(self, timeout: float = 15.0):
        super().__init__(
            base_url="https://wstransparencia.vitoria.es.gov.br",
            timeout=timeout,
        )

    async def buscar_despesas_fornecedor(
        self,
        cnpj: str,
        exercicio: int,
        mes: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca despesas pagas a um fornecedor (CNPJ) em Vitória.

        Args:
            cnpj: CNPJ do fornecedor (MEI)
            exercicio: Ano fiscal
            mes: Mês (1-12), opcional
        """
        cnpj_limpo = self.validate_cnpj(cnpj)

        params: Dict[str, Any] = {
            "cnpj": cnpj_limpo,
            "exercicio": exercicio,
        }
        if mes:
            params["mes"] = mes

        logger.info(
            "[%s] Buscando despesas para %s em Vitória (exercício=%d)",
            self.SERVICE_NAME,
            self.mask_cnpj(cnpj_limpo),
            exercicio,
        )

        # Endpoint real — confirmar na documentação oficial
        data = await self._request("GET", "/api/despesa/fornecedor", params=params)

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("registros", []))
        return []

    async def buscar_despesas_secretaria(
        self,
        exercicio: int,
        mes: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Despesas por secretaria (panorama geral)."""
        params: Dict[str, Any] = {"exercicio": exercicio}
        if mes:
            params["mes"] = mes

        data = await self._request("GET", "/api/despesa/secretaria", params=params)
        return data if isinstance(data, list) else []

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
                orgao=reg.get("secretaria", reg.get("orgao", "Prefeitura de Vitória")),
                valor=float(reg.get("valor", reg.get("valorPago", 0))),
                ano=reg.get("exercicio"),
                mes=reg.get("mes"),
                fonte="transparencia_vitoria",
            ))
        return resultado
