"""
Domain models — NFSe e Transparência.

Modelos para dados de Nota Fiscal de Serviço Eletrônica
e dados de transparência pública (federal / municipal).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── NFSe ─────────────────────────────────────────────────────────────────────

class NFSeStatus(str, Enum):
    EMITIDA = "emitida"
    CANCELADA = "cancelada"
    SUBSTITUIDA = "substituida"
    PENDENTE = "pendente"
    ERRO = "erro"


class NFSeResumo(BaseModel):
    """Resumo de uma NFSe emitida ou consultada."""

    numero: Optional[str] = None
    codigo_verificacao: Optional[str] = None
    status: NFSeStatus = NFSeStatus.PENDENTE

    cnpj_prestador: str = ""
    razao_social_prestador: Optional[str] = None
    municipio_prestacao: Optional[str] = None

    cnpj_tomador: Optional[str] = None
    razao_social_tomador: Optional[str] = None

    descricao_servico: Optional[str] = None
    valor_servico: float = Field(0.0)
    valor_iss: float = Field(0.0)
    aliquota_iss: float = Field(0.0)

    data_emissao: Optional[datetime] = None
    competencia: Optional[str] = Field(None, description="Competência MM/YYYY")

    # Metadados
    fonte: str = Field("unknown", description="emissor_nacional, focus_nfe, webmania, etc.")
    id_externo: Optional[str] = Field(None, description="ID na API do provedor")


class EmissaoNFSeRequest(BaseModel):
    """Dados necessários para emitir uma NFSe via agregador ou Emissor Nacional."""

    # Prestador (MEI)
    cnpj_prestador: str
    inscricao_municipal: Optional[str] = None

    # Tomador
    cnpj_tomador: Optional[str] = None
    cpf_tomador: Optional[str] = None
    razao_social_tomador: Optional[str] = None
    email_tomador: Optional[str] = None

    # Serviço
    descricao_servico: str
    valor_servico: float
    codigo_servico: Optional[str] = Field(None, description="Código do serviço municipal/LC 116")
    cnae: Optional[str] = None
    codigo_tributacao_municipio: Optional[str] = None

    # ISS
    iss_retido: bool = False
    aliquota_iss: Optional[float] = None

    # Competência
    competencia: Optional[str] = Field(None, description="MM/YYYY")

    # Opcional
    observacoes: Optional[str] = None


# ── Transparência ────────────────────────────────────────────────────────────

class PagamentoGoverno(BaseModel):
    """Pagamento recebido por um CNPJ de órgão público."""

    cnpj_favorecido: str
    nome_favorecido: Optional[str] = None

    orgao: Optional[str] = None
    unidade_gestora: Optional[str] = None
    funcao: Optional[str] = None

    valor: float = Field(0.0)
    data_pagamento: Optional[date] = None
    ano: Optional[int] = None
    mes: Optional[int] = None

    tipo_documento: Optional[str] = None
    numero_documento: Optional[str] = None

    fonte: str = Field("unknown", description="transparencia_federal, vitoria, serra, etc.")


class ResumoTransparencia(BaseModel):
    """Resumo consolidado de dados de transparência para um CNPJ."""

    cnpj: str
    total_pagamentos: int = 0
    valor_total: float = Field(0.0)

    # Breakdown por esfera
    pagamentos_federais: int = 0
    valor_federal: float = Field(0.0)

    pagamentos_municipais: int = 0
    valor_municipal: float = Field(0.0)

    # Detalhes
    pagamentos: List[PagamentoGoverno] = Field(default_factory=list)
    orgaos_pagadores: List[str] = Field(default_factory=list)

    periodo_inicio: Optional[date] = None
    periodo_fim: Optional[date] = None
