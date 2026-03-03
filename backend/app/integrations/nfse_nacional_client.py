"""
Client — Emissor Nacional NFS-e (padrão federal 2026+).

Sistema Nacional Nota Fiscal de Serviço Eletrônica.
Documentação técnica:
https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica

APIs para envio de DPS (Declaração de Prestação de Serviços),
consulta, cancelamento e substituição.

Env vars:
- NFSE_NACIONAL_BASE_URL: URL base (homologação ou produção)
- NFSE_NACIONAL_TOKEN: Token de acesso / certificado digital
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from .http_base import ExternalAPIClient, ExternalAPIError
from .domain.nfse_transparencia_models import EmissaoNFSeRequest, NFSeResumo, NFSeStatus

logger = logging.getLogger(__name__)

# URLs do Emissor Nacional
NFSE_NACIONAL_HOMOLOGACAO = "https://sefin.nfse.gov.br/sefinnacional-homologacao"
NFSE_NACIONAL_PRODUCAO = "https://sefin.nfse.gov.br/sefinnacional"


class NFSeNacionalClient(ExternalAPIClient):
    """
    Client para API do Emissor Público Nacional de NFS-e.

    Obrigatório para MEI em municípios conveniados (2026+).
    Suporta envio de DPS (Declaração de Prestação de Serviço),
    consulta e cancelamento.

    NOTA: Esta integração requer certificado digital e/ou
    credenciamento no portal gov.br. Os endpoints e payloads
    seguem a documentação técnica oficial.
    """

    SERVICE_NAME = "nfse-nacional"

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        homologacao: bool = True,
        timeout: float = 30.0,
    ):
        _token = token or os.getenv("NFSE_NACIONAL_TOKEN", "")
        url = base_url or os.getenv("NFSE_NACIONAL_BASE_URL", "")

        if not url:
            url = NFSE_NACIONAL_HOMOLOGACAO if homologacao else NFSE_NACIONAL_PRODUCAO

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if _token:
            headers["Authorization"] = f"Bearer {_token}"

        super().__init__(base_url=url, timeout=timeout, headers=headers)
        self.homologacao = homologacao

    @property
    def ambiente(self) -> str:
        return "homologacao" if self.homologacao else "producao"

    async def enviar_dps(self, request: EmissaoNFSeRequest) -> NFSeResumo:
        """
        Envia DPS (Declaração de Prestação de Serviço) ao Emissor Nacional.

        O DPS é processado assincronamente pelo sistema.
        Após envio, use consultar_nfse() para obter o resultado.
        """
        logger.info(
            "[%s] Enviando DPS para %s (ambiente=%s, valor=R$%.2f)",
            self.SERVICE_NAME,
            self.mask_cnpj(request.cnpj_prestador),
            self.ambiente,
            request.valor_servico,
        )

        payload = self._build_dps_payload(request)

        data = await self._request(
            "POST",
            "/contribuinte/dps",
            json_body=payload,
            expected_status=201,
        )

        if not isinstance(data, dict):
            raise ExternalAPIError(
                "Resposta inesperada ao enviar DPS",
                service=self.SERVICE_NAME,
            )

        return NFSeResumo(
            numero=str(data.get("numero", "")),
            codigo_verificacao=data.get("codigoVerificacao"),
            status=NFSeStatus.PENDENTE,
            cnpj_prestador=self.clean_cnpj(request.cnpj_prestador),
            valor_servico=request.valor_servico,
            descricao_servico=request.descricao_servico,
            fonte="emissor_nacional",
            id_externo=str(data.get("id", data.get("chaveAcesso", ""))),
        )

    async def consultar_nfse(
        self,
        chave_acesso: Optional[str] = None,
        numero: Optional[str] = None,
        cnpj: Optional[str] = None,
    ) -> NFSeResumo:
        """Consulta NFSe por chave de acesso ou número."""
        params: Dict[str, str] = {}

        if chave_acesso:
            path = f"/contribuinte/nfse/{chave_acesso}"
        elif numero and cnpj:
            path = "/contribuinte/nfse"
            params = {"numero": numero, "cnpj": self.clean_cnpj(cnpj)}
        else:
            raise ValueError("Forneça chave_acesso ou (numero + cnpj)")

        data = await self._request("GET", path, params=params or None)

        if not isinstance(data, dict):
            raise ExternalAPIError(
                "Resposta inesperada ao consultar NFSe Nacional",
                service=self.SERVICE_NAME,
            )

        return self._parse_response(data)

    async def cancelar_nfse(self, chave_acesso: str, motivo: str = "") -> Dict[str, Any]:
        """Cancela uma NFSe pelo Emissor Nacional."""
        payload: Dict[str, Any] = {}
        if motivo:
            payload["justificativa"] = motivo

        data = await self._request(
            "POST",
            f"/contribuinte/nfse/{chave_acesso}/cancelamento",
            json_body=payload or None,
        )

        return data if isinstance(data, dict) else {"status": "cancelamento_solicitado"}

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_dps_payload(self, req: EmissaoNFSeRequest) -> Dict[str, Any]:
        """Constrói payload DPS conforme especificação do Emissor Nacional."""
        payload: Dict[str, Any] = {
            "infDPS": {
                "tpAmb": 2 if self.homologacao else 1,  # 1=Produção, 2=Homologação
                "dhEmi": "",  # Será preenchido pelo sistema
                "verAplic": "NEXUS-1.0",
                "prest": {
                    "CNPJ": self.clean_cnpj(req.cnpj_prestador),
                },
                "serv": {
                    "cServ": {
                        "cTribNac": req.codigo_servico or "",
                        "xDescServ": req.descricao_servico,
                    },
                    "vServPrest": {
                        "vServ": f"{req.valor_servico:.2f}",
                    },
                },
            }
        }

        # Inscricao municipal
        if req.inscricao_municipal:
            payload["infDPS"]["prest"]["IM"] = req.inscricao_municipal

        # Tomador
        if req.cnpj_tomador or req.cpf_tomador:
            tomador: Dict[str, Any] = {}
            if req.cnpj_tomador:
                tomador["CNPJ"] = self.clean_cnpj(req.cnpj_tomador)
            elif req.cpf_tomador:
                tomador["CPF"] = "".join(filter(str.isdigit, req.cpf_tomador))
            if req.razao_social_tomador:
                tomador["xNome"] = req.razao_social_tomador
            if req.email_tomador:
                tomador["email"] = req.email_tomador
            payload["infDPS"]["toma"] = tomador

        # ISS
        if req.aliquota_iss is not None:
            payload["infDPS"]["serv"]["vServPrest"]["trib"] = {
                "totTrib": {
                    "pAliqAplic": f"{req.aliquota_iss:.4f}",
                }
            }

        return payload

    def _parse_response(self, data: Dict[str, Any]) -> NFSeResumo:
        """Parse de resposta do Emissor Nacional em NFSeResumo."""
        # Status
        sit = str(data.get("situacao", data.get("status", ""))).lower()
        status_map = {
            "normal": NFSeStatus.EMITIDA,
            "emitida": NFSeStatus.EMITIDA,
            "cancelada": NFSeStatus.CANCELADA,
            "substituida": NFSeStatus.SUBSTITUIDA,
        }
        status = status_map.get(sit, NFSeStatus.PENDENTE)

        # Valor
        serv = data.get("infNFSe", {}).get("serv", {})
        valor = float(serv.get("vServPrest", {}).get("vServ", 0))

        return NFSeResumo(
            numero=str(data.get("numero", "")),
            codigo_verificacao=data.get("codigoVerificacao"),
            status=status,
            cnpj_prestador=data.get("infNFSe", {}).get("prest", {}).get("CNPJ", ""),
            valor_servico=valor,
            descricao_servico=serv.get("cServ", {}).get("xDescServ", ""),
            fonte="emissor_nacional",
            id_externo=data.get("chaveAcesso", ""),
        )
