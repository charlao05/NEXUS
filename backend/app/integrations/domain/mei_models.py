"""
Domain models — MEI Profile, Cadastro, Obrigações.

Representa os dados estruturados que o NEXUS consome
das APIs de CNPJ / Portal do Empreendedor / PGMEI.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class SituacaoCadastral(str, Enum):
    ATIVA = "ativa"
    SUSPENSA = "suspensa"
    INAPTA = "inapta"
    BAIXADA = "baixada"
    NULA = "nula"
    DESCONHECIDA = "desconhecida"


class AtividadeTipo(str, Enum):
    COMERCIO = "comercio"
    SERVICO = "servico"
    INDUSTRIA = "industria"
    MISTO = "misto"


# ── Models ───────────────────────────────────────────────────────────────────

class CNAEInfo(BaseModel):
    """Código Nacional de Atividade Econômica."""
    codigo: str = Field(..., description="Código CNAE (ex: 4711302)")
    descricao: str = Field("", description="Descrição da atividade")


class MEIProfile(BaseModel):
    """Perfil consolidado do MEI a partir de dados de CNPJ."""

    cnpj: str = Field(..., description="CNPJ (14 dígitos, sem máscara)")
    razao_social: str = Field(..., description="Razão social / nome empresarial")
    nome_fantasia: Optional[str] = Field(None, description="Nome fantasia")
    cpf_responsavel: Optional[str] = Field(None, description="CPF do responsável (mascarado)")

    # Classificação
    is_mei: bool = Field(False, description="Se é MEI (SIMEI)")
    is_simples: bool = Field(False, description="Se é optante do Simples Nacional")
    natureza_juridica: str = Field("", description="Natureza jurídica (código + descrição)")

    # Situação
    situacao_cadastral: SituacaoCadastral = Field(SituacaoCadastral.DESCONHECIDA)
    data_situacao_cadastral: Optional[date] = None
    data_abertura: Optional[date] = None

    # Localização
    uf: str = Field("", max_length=2)
    municipio: str = Field("")
    cep: Optional[str] = None
    logradouro: Optional[str] = None
    bairro: Optional[str] = None

    # Atividade
    cnae_principal: Optional[CNAEInfo] = None
    cnaes_secundarios: List[CNAEInfo] = Field(default_factory=list)
    tipo_atividade: AtividadeTipo = Field(AtividadeTipo.SERVICO)

    # Simples / SIMEI datas
    data_opcao_simples: Optional[date] = None
    data_opcao_mei: Optional[date] = None

    # Metadados
    fonte: str = Field("unknown", description="Fonte dos dados (opencnpj, cnpja, cnpjws, etc.)")
    consultado_em: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_cnpj_payload(cls, payload: dict, *, fonte: str = "unknown") -> "MEIProfile":
        """
        Constrói MEIProfile a partir de um payload genérico de API de CNPJ.
        Aceita campos em pt/en e variantes (tolerância de parsing).
        """
        # Extrair flags MEI / Simples
        simples = payload.get("simples", payload.get("opcao_simples", {}))
        if isinstance(simples, dict):
            is_simples = simples.get("optante", simples.get("simples", False))
            is_mei = simples.get("mei", simples.get("simei", False))
        else:
            is_simples = bool(simples)
            is_mei = False

        # Inferir MEI pela natureza jurídica (213-5)
        natureza = payload.get("natureza_juridica", "")
        if isinstance(natureza, dict):
            natureza_str = f"{natureza.get('codigo', '')} - {natureza.get('descricao', '')}"
        else:
            natureza_str = str(natureza)

        if not is_mei and "213-5" in natureza_str:
            is_mei = True
        if not is_mei and "microempreendedor individual" in natureza_str.lower():
            is_mei = True

        # Situação cadastral
        sit_raw = (
            payload.get("situacao_cadastral", "")
            or payload.get("situacao", "")
            or payload.get("status", "")
        )
        if isinstance(sit_raw, dict):
            sit_raw = sit_raw.get("descricao", sit_raw.get("id", ""))
        sit_str = str(sit_raw).strip().lower()

        situacao_map = {
            "ativa": SituacaoCadastral.ATIVA,
            "suspensa": SituacaoCadastral.SUSPENSA,
            "inapta": SituacaoCadastral.INAPTA,
            "baixada": SituacaoCadastral.BAIXADA,
            "nula": SituacaoCadastral.NULA,
            "02": SituacaoCadastral.ATIVA,  # Código RFB
            "04": SituacaoCadastral.INAPTA,
            "08": SituacaoCadastral.BAIXADA,
        }
        situacao = situacao_map.get(sit_str, SituacaoCadastral.DESCONHECIDA)

        # CNAE
        cnae_raw = payload.get("cnae_fiscal_principal", payload.get("cnae_principal", {}))
        cnae_principal = None
        if isinstance(cnae_raw, dict):
            cnae_principal = CNAEInfo(
                codigo=str(cnae_raw.get("codigo", cnae_raw.get("code", ""))),
                descricao=cnae_raw.get("descricao", cnae_raw.get("description", "")),
            )
        elif isinstance(cnae_raw, (str, int)):
            cnae_principal = CNAEInfo(codigo=str(cnae_raw), descricao="")

        cnaes_sec = []
        for sec in payload.get("cnaes_secundarios", payload.get("cnaes_secundarias", [])):
            if isinstance(sec, dict):
                cnaes_sec.append(CNAEInfo(
                    codigo=str(sec.get("codigo", sec.get("code", ""))),
                    descricao=sec.get("descricao", sec.get("description", "")),
                ))

        # Datas
        def parse_date(val: Any) -> Optional[date]:
            if not val:
                return None
            if isinstance(val, date):
                return val
            try:
                return date.fromisoformat(str(val)[:10])
            except (ValueError, TypeError):
                return None

        # Endereço (aceita variantes)
        endereco = payload.get("endereco", payload.get("estabelecimento", payload))

        return cls(
            cnpj="".join(filter(str.isdigit, str(payload.get("cnpj", "")))),
            razao_social=(
                payload.get("razao_social")
                or payload.get("nome_empresarial")
                or payload.get("company", {}).get("name", "")
                or ""
            ),
            nome_fantasia=payload.get("nome_fantasia") or payload.get("alias"),
            is_mei=is_mei,
            is_simples=is_simples,
            natureza_juridica=natureza_str,
            situacao_cadastral=situacao,
            data_situacao_cadastral=parse_date(payload.get("data_situacao_cadastral")),
            data_abertura=parse_date(
                payload.get("data_abertura")
                or payload.get("data_inicio_atividade")
                or payload.get("founded")
            ),
            uf=str(endereco.get("uf", endereco.get("state", "")) if isinstance(endereco, dict) else ""),
            municipio=str(endereco.get("municipio", endereco.get("city", "")) if isinstance(endereco, dict) else ""),
            cep=str(endereco.get("cep", "") if isinstance(endereco, dict) else "") or None,
            logradouro=str(endereco.get("logradouro", "") if isinstance(endereco, dict) else "") or None,
            bairro=str(endereco.get("bairro", "") if isinstance(endereco, dict) else "") or None,
            cnae_principal=cnae_principal,
            cnaes_secundarios=cnaes_sec,
            data_opcao_simples=parse_date(
                simples.get("data_opcao") if isinstance(simples, dict) else None
            ),
            data_opcao_mei=parse_date(
                simples.get("data_opcao_mei") if isinstance(simples, dict) else None
            ),
            fonte=fonte,
        )


class ObrigacoesMEI(BaseModel):
    """Obrigações correntes do MEI com prazos e status."""

    cnpj: str

    # DAS mensal
    das_valor_mensal: float = Field(0.0, description="Valor estimado do DAS (R$)")
    das_proximo_vencimento: Optional[date] = None
    das_componentes: dict = Field(
        default_factory=dict,
        description="Componentes: inss, iss, icms (R$)",
    )

    # DASN-SIMEI (declaração anual)
    dasn_ano_referencia: Optional[int] = None
    dasn_prazo: Optional[date] = None
    dasn_entregue: Optional[bool] = None

    # NFSe
    nfse_obrigatoria: bool = Field(False, description="Se emissão de NFSe é obrigatória")
    nfse_emissor_nacional: bool = Field(
        True,
        description="Se deve usar Emissor Nacional (padrão 2026+)",
    )

    # Links úteis
    link_pgmei: str = Field(
        "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/pgmei.app/Identificacao",
        description="Link oficial para emitir DAS",
    )
    link_dasn: str = Field(
        "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/dasnsimei.app/Identificacao",
        description="Link oficial para DASN-SIMEI",
    )
    link_app_mei: str = Field(
        "https://www.gov.br/pt-br/apps/mei",
        description="App oficial MEI",
    )


class DiagnosticoMEI(BaseModel):
    """Diagnóstico completo do MEI — combina perfil + obrigações + fiscal."""

    perfil: MEIProfile
    obrigacoes: ObrigacoesMEI
    alertas: List[str] = Field(default_factory=list)
    recomendacoes: List[str] = Field(default_factory=list)

    # Dados opcionais de transparência
    pagamentos_governo_federal: int = Field(0, description="Nº de pagamentos recebidos da União")
    valor_total_governo: float = Field(0.0, description="Valor total recebido de órgãos públicos (R$)")
