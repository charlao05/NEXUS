"""
Router — Integrações Governamentais MEI.

Endpoints:
  POST /api/gov/mei/diagnostico      — Diagnóstico completo do MEI
  GET  /api/gov/mei/{cnpj}           — Perfil MEI (cadastro CNPJ)
  GET  /api/gov/mei/{cnpj}/obrigacoes — Obrigações correntes
  GET  /api/gov/mei/{cnpj}/fiscal    — Situação fiscal (CND + Dívida Ativa)
  GET  /api/gov/mei/{cnpj}/transparencia — Pagamentos do governo

Todos os endpoints requerem autenticação (Depends(get_current_user)).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gov", tags=["gov-integrations"])


# ── Schemas de Request/Response ──────────────────────────────────────────────

class DiagnosticoRequest(BaseModel):
    cnpj: str = Field(..., description="CNPJ do MEI (com ou sem máscara)")
    incluir_fiscal: bool = Field(True, description="Consultar CND + Dívida Ativa")
    incluir_transparencia: bool = Field(False, description="Consultar Portal da Transparência")
    ano_transparencia: Optional[int] = Field(None, description="Ano para transparência")


class ErrorResponse(BaseModel):
    detail: str
    service: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_current_user():
    """Dependency de autenticação — importa get_current_user do auth."""
    try:
        from app.api.auth import get_current_user
        return Depends(get_current_user)
    except ImportError:
        return None


def _validate_cnpj_param(cnpj: str) -> str:
    """Valida e limpa CNPJ de path parameter."""
    digits = re.sub(r"\D", "", cnpj)
    if len(digits) != 14:
        raise HTTPException(
            status_code=400,
            detail=f"CNPJ inválido: esperado 14 dígitos, recebido {len(digits)}",
        )
    return digits


# ── Dependency de autenticação ───────────────────────────────────────────────

try:
    from app.api.auth import get_current_user as _auth_dep  # type: ignore[import]
except ImportError:
    # Fallback para desenvolvimento sem auth
    async def _auth_dep():  # type: ignore[misc]
        return {"id": 0, "email": "dev@local", "role": "admin"}


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/mei/diagnostico", summary="Diagnóstico completo do MEI")
async def diagnosticar_mei(
    body: DiagnosticoRequest,
    user=Depends(_auth_dep),
):
    """
    Realiza diagnóstico completo de um MEI:
    - Dados cadastrais (CNPJ, situação, CNAE, flag MEI)
    - Obrigações (DAS, DASN-SIMEI, NFSe)
    - Situação fiscal (CND, Dívida Ativa) — se configurado
    - Pagamentos do governo — se solicitado

    **Requer autenticação.**
    """
    from app.integrations.services.mei_service import MEIService
    from app.integrations.http_base import ExternalAPIClientError, ExternalAPIError

    service = MEIService()

    try:
        resultado = await service.diagnosticar_mei(
            body.cnpj,
            incluir_fiscal=body.incluir_fiscal,
            incluir_transparencia=body.incluir_transparencia,
            ano_transparencia=body.ano_transparencia,
        )
        return resultado.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExternalAPIClientError as e:
        raise HTTPException(
            status_code=e.status_code or 400,
            detail=f"Erro na consulta: {e}",
        )
    except ExternalAPIError as e:
        logger.error("Erro em API externa: %s", e, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"Serviço externo indisponível ({e.service}): {e}",
        )


@router.get("/mei/{cnpj}", summary="Perfil do MEI (cadastro CNPJ)")
async def get_mei_profile(
    cnpj: str,
    user=Depends(_auth_dep),
):
    """
    Consulta dados cadastrais de um CNPJ e retorna se é MEI.

    Fontes: BrasilAPI → OpenCNPJ → CNPJá (fallback automático).
    """
    from app.integrations.services.mei_service import MEIService
    from app.integrations.http_base import ExternalAPIClientError, ExternalAPIError

    cnpj_limpo = _validate_cnpj_param(cnpj)
    service = MEIService()

    try:
        profile = await service.consultar_perfil(cnpj_limpo)
        return profile.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExternalAPIClientError as e:
        status = e.status_code or 404
        raise HTTPException(status_code=status, detail=f"CNPJ não encontrado: {e}")
    except ExternalAPIError as e:
        raise HTTPException(status_code=502, detail=f"Serviço indisponível: {e}")


@router.get("/mei/{cnpj}/obrigacoes", summary="Obrigações correntes do MEI")
async def get_mei_obrigacoes(
    cnpj: str,
    user=Depends(_auth_dep),
):
    """
    Retorna obrigações do MEI: DAS mensal (valor + vencimento),
    DASN-SIMEI (prazo), NFSe (obrigatoriedade).

    Calculado com base no CNAE e tabela DAS 2026.
    """
    from app.integrations.services.mei_service import MEIService, _calcular_obrigacoes
    from app.integrations.http_base import ExternalAPIError

    cnpj_limpo = _validate_cnpj_param(cnpj)
    service = MEIService()

    try:
        profile = await service.consultar_perfil(cnpj_limpo)
        obrigacoes = _calcular_obrigacoes(profile)
        return obrigacoes.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExternalAPIError as e:
        raise HTTPException(status_code=502, detail=f"Serviço indisponível: {e}")


@router.get("/mei/{cnpj}/fiscal", summary="Situação fiscal do MEI")
async def get_mei_fiscal(
    cnpj: str,
    user=Depends(_auth_dep),
):
    """
    Consulta situação fiscal: CND e Dívida Ativa.

    Depende de configuração de provedores:
    - CND_PROVIDER + CND_API_KEY
    - DIVIDA_ATIVA_PROVIDER + DIVIDA_ATIVA_API_KEY

    Se não configurados, retorna status "indisponível" / "mock".
    """
    from app.integrations.services.mei_service import MEIService
    from app.integrations.http_base import ExternalAPIError

    cnpj_limpo = _validate_cnpj_param(cnpj)
    service = MEIService()

    try:
        fiscal = await service._consultar_fiscal(cnpj_limpo)
        if fiscal:
            fiscal.calcular_indicadores()
            return fiscal.model_dump()
        return {"cnpj": cnpj_limpo, "message": "Consulta fiscal não disponível"}
    except ExternalAPIError as e:
        raise HTTPException(status_code=502, detail=f"Serviço indisponível: {e}")


@router.get("/mei/{cnpj}/transparencia", summary="Pagamentos do governo ao MEI")
async def get_mei_transparencia(
    cnpj: str,
    ano: Optional[int] = Query(None, description="Filtrar por ano"),
    user=Depends(_auth_dep),
):
    """
    Consulta pagamentos recebidos pelo CNPJ de órgãos do governo federal.

    Requer: TRANSPARENCIA_API_KEY (chave gratuita do Portal da Transparência).
    """
    from app.integrations.transparencia_federal_client import TransparenciaFederalClient
    from app.integrations.http_base import ExternalAPIError

    cnpj_limpo = _validate_cnpj_param(cnpj)

    try:
        async with TransparenciaFederalClient() as client:
            resumo = await client.resumo_pagamentos(cnpj_limpo, ano=ano)
            return resumo.model_dump()
    except ExternalAPIError as e:
        raise HTTPException(status_code=502, detail=f"Portal da Transparência indisponível: {e}")


# ── Endpoints informativos (sem auth) ───────────────────────────────────────

@router.get("/info/provedores", summary="Lista provedores configurados")
async def get_provedores_configurados():
    """
    Retorna quais integrações governamentais estão configuradas
    (sem expor chaves/secrets).
    """
    import os

    return {
        "cnpj": {
            "provedor_padrao": "brasilapi",
            "provedores_disponiveis": ["brasilapi", "opencnpj", "cnpja", "cnpjws"],
        },
        "cnd": {
            "provedor": os.getenv("CND_PROVIDER", "mock"),
            "configurado": bool(os.getenv("CND_API_KEY")),
        },
        "divida_ativa": {
            "provedor": os.getenv("DIVIDA_ATIVA_PROVIDER", "mock"),
            "configurado": bool(os.getenv("DIVIDA_ATIVA_API_KEY")),
        },
        "transparencia_federal": {
            "configurado": bool(os.getenv("TRANSPARENCIA_API_KEY")),
        },
        "nfse_agregador": {
            "provedor": os.getenv("NFSE_AGGREGATOR_PROVIDER", "não configurado"),
            "configurado": bool(os.getenv("NFSE_AGGREGATOR_API_KEY")),
        },
        "nfse_nacional": {
            "configurado": bool(os.getenv("NFSE_NACIONAL_TOKEN")),
            "ambiente": "homologacao" if not os.getenv("NFSE_NACIONAL_BASE_URL", "").endswith("nacional") else "producao",
        },
    }


@router.get("/info/das-tabela", summary="Tabela DAS-MEI 2026")
async def get_tabela_das():
    """Retorna tabela de valores DAS-MEI 2026 por tipo de atividade."""
    from app.integrations.services.mei_service import _DAS_COMPONENTES

    return {
        "ano_referencia": 2026,
        "salario_minimo": 1621.00,
        "aliquota_inss": "5%",
        "tabela": {
            tipo.value: {
                "inss": comp["inss"],
                "icms": comp["icms"],
                "iss": comp["iss"],
                "total": comp["total"],
            }
            for tipo, comp in _DAS_COMPONENTES.items()
        },
        "links": {
            "pgmei": "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/pgmei.app/Identificacao",
            "app_mei": "https://www.gov.br/pt-br/apps/mei",
            "emissor_nfse": "https://www.nfse.gov.br/EmissorNacional",
        },
    }
