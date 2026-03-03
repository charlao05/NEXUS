"""
Client — NFSe via Agregadores (Focus NFe, Webmania, Nuvem Fiscal, NFE.io).

Abstrai emissão e consulta de NFSe multi-municípios com uma única API REST.
Útil para MEIs em municípios ainda não migrados para o Emissor Nacional.

Env vars:
- NFSE_AGGREGATOR_PROVIDER: "focus_nfe" | "webmania" | "nuvem_fiscal" | "nfe_io"
- NFSE_AGGREGATOR_API_KEY: Chave da API do agregador
- NFSE_AGGREGATOR_BASE_URL: URL base (opcional, inferida do provider)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from .http_base import ExternalAPIClient, ExternalAPIError
from .domain.nfse_transparencia_models import EmissaoNFSeRequest, NFSeResumo, NFSeStatus

logger = logging.getLogger(__name__)


_PROVIDER_URLS = {
    "focus_nfe": "https://api.focusnfe.com.br",
    "webmania": "https://webmaniabr.com/api/1",
    "nuvem_fiscal": "https://api.nuvemfiscal.com.br",
    "nfe_io": "https://api.nfe.io",
}


class NFSeAggregatorClient(ExternalAPIClient):
    """
    Client genérico para APIs de agregadores de NFSe.

    Cada provedor tem seu payload/response específico;
    esta classe padroniza a interface para o NEXUS.
    """

    SERVICE_NAME = "nfse-aggregator"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.provider = provider or os.getenv("NFSE_AGGREGATOR_PROVIDER", "focus_nfe")
        key = api_key or os.getenv("NFSE_AGGREGATOR_API_KEY", "")

        url = base_url or _PROVIDER_URLS.get(self.provider, "")
        if not url:
            raise ValueError(f"URL não configurada para provedor NFSe: {self.provider}")

        headers = {
            "Content-Type": "application/json",
        }
        # Cada provedor usa um esquema de autenticação diferente
        if key:
            if self.provider == "focus_nfe":
                # Focus NFe usa HTTP Basic Auth (token:)
                import base64
                encoded = base64.b64encode(f"{key}:".encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"
            elif self.provider in ("webmania", "nuvem_fiscal"):
                headers["Authorization"] = f"Bearer {key}"
            elif self.provider == "nfe_io":
                headers["Authorization"] = key

        super().__init__(base_url=url, timeout=timeout, headers=headers)

    async def emitir_nfse(self, request: EmissaoNFSeRequest) -> NFSeResumo:
        """
        Emite uma NFSe via o agregador.

        Args:
            request: Dados da NFSe a emitir

        Returns:
            NFSeResumo com número, status e dados da emissão
        """
        logger.info(
            "[%s] Emitindo NFSe para %s via %s (valor=R$%.2f)",
            self.SERVICE_NAME,
            self.mask_cnpj(request.cnpj_prestador),
            self.provider,
            request.valor_servico,
        )

        payload = self._build_emissao_payload(request)
        path = self._emissao_path()

        data = await self._request("POST", path, json_body=payload, expected_status=201)

        if not isinstance(data, dict):
            # Alguns provedores retornam 200 em vez de 201
            if data is None:
                raise ExternalAPIError(
                    "Resposta vazia ao emitir NFSe",
                    service=self.SERVICE_NAME,
                )

        return self._parse_nfse_response(data, request.cnpj_prestador)

    async def consultar_nfse(self, id_nfse: str) -> NFSeResumo:
        """
        Consulta status de uma NFSe pelo ID do provedor.
        """
        path = self._consulta_path(id_nfse)
        data = await self._request("GET", path)

        if not isinstance(data, dict):
            raise ExternalAPIError(
                "Resposta inesperada ao consultar NFSe",
                service=self.SERVICE_NAME,
            )

        return self._parse_nfse_response(data)

    async def cancelar_nfse(self, id_nfse: str, justificativa: str = "") -> Dict[str, Any]:
        """Cancela uma NFSe via o agregador."""
        path = self._cancelamento_path(id_nfse)
        payload = {"justificativa": justificativa} if justificativa else {}

        data = await self._request("DELETE", path, json_body=payload or None)
        return data if isinstance(data, dict) else {"status": "cancelado"}

    # ── Helpers por provedor ─────────────────────────────────────────────────

    def _emissao_path(self) -> str:
        paths = {
            "focus_nfe": "/v2/nfse",
            "webmania": "/nfse/emissao",
            "nuvem_fiscal": "/nfse",
            "nfe_io": "/v1/companies/default/serviceinvoices",
        }
        return paths.get(self.provider, "/nfse")

    def _consulta_path(self, id_nfse: str) -> str:
        paths = {
            "focus_nfe": f"/v2/nfse/{id_nfse}",
            "webmania": f"/nfse/consulta/{id_nfse}",
            "nuvem_fiscal": f"/nfse/{id_nfse}",
            "nfe_io": f"/v1/companies/default/serviceinvoices/{id_nfse}",
        }
        return paths.get(self.provider, f"/nfse/{id_nfse}")

    def _cancelamento_path(self, id_nfse: str) -> str:
        paths = {
            "focus_nfe": f"/v2/nfse/{id_nfse}",
            "webmania": f"/nfse/cancelamento/{id_nfse}",
            "nuvem_fiscal": f"/nfse/{id_nfse}/cancelamento",
            "nfe_io": f"/v1/companies/default/serviceinvoices/{id_nfse}",
        }
        return paths.get(self.provider, f"/nfse/{id_nfse}/cancelar")

    def _build_emissao_payload(self, req: EmissaoNFSeRequest) -> Dict[str, Any]:
        """Constrói payload de emissão adaptado ao provedor."""
        # Payload genérico compatível com Focus NFe
        payload: Dict[str, Any] = {
            "prestador": {
                "cnpj": self.clean_cnpj(req.cnpj_prestador),
                "inscricao_municipal": req.inscricao_municipal or "",
            },
            "servico": {
                "discriminacao": req.descricao_servico,
                "valor_servicos": req.valor_servico,
                "iss_retido": req.iss_retido,
            },
        }

        if req.aliquota_iss is not None:
            payload["servico"]["aliquota"] = req.aliquota_iss

        if req.codigo_servico:
            payload["servico"]["item_lista_servico"] = req.codigo_servico

        # Tomador
        tomador: Dict[str, Any] = {}
        if req.cnpj_tomador:
            tomador["cnpj"] = self.clean_cnpj(req.cnpj_tomador)
        elif req.cpf_tomador:
            tomador["cpf"] = "".join(filter(str.isdigit, req.cpf_tomador))
        if req.razao_social_tomador:
            tomador["razao_social"] = req.razao_social_tomador
        if req.email_tomador:
            tomador["email"] = req.email_tomador
        if tomador:
            payload["tomador"] = tomador

        return payload

    def _parse_nfse_response(
        self,
        data: Any,
        cnpj_prestador: str = "",
    ) -> NFSeResumo:
        """Parse genérico de resposta NFSe (tolerante a variações de provedor)."""
        if not isinstance(data, dict):
            data = {}

        status_raw = str(data.get("status", data.get("situacao", "pendente"))).lower()
        status_map = {
            "autorizada": NFSeStatus.EMITIDA,
            "emitida": NFSeStatus.EMITIDA,
            "concluida": NFSeStatus.EMITIDA,
            "issued": NFSeStatus.EMITIDA,
            "cancelada": NFSeStatus.CANCELADA,
            "cancelled": NFSeStatus.CANCELADA,
            "substituida": NFSeStatus.SUBSTITUIDA,
            "erro": NFSeStatus.ERRO,
            "error": NFSeStatus.ERRO,
            "rejeitada": NFSeStatus.ERRO,
        }
        status = status_map.get(status_raw, NFSeStatus.PENDENTE)

        return NFSeResumo(
            numero=str(data.get("numero", data.get("number", ""))),
            codigo_verificacao=data.get("codigo_verificacao", data.get("verification_code")),
            status=status,
            cnpj_prestador=cnpj_prestador or data.get("cnpj_prestador", ""),
            valor_servico=float(data.get("valor_servicos", data.get("valor", 0))),
            valor_iss=float(data.get("valor_iss", 0)),
            descricao_servico=data.get("discriminacao", data.get("descricao", "")),
            fonte=self.provider,
            id_externo=str(data.get("id", data.get("ref", ""))),
        )
