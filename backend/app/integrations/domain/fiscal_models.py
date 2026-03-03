"""
Domain models — Situação Fiscal, CND, Dívida Ativa.

Modelos para dados de regularidade fiscal do MEI junto
à Receita Federal, PGFN e Conecta gov.br.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class TipoCertidao(str, Enum):
    NEGATIVA = "negativa"                        # Sem débitos
    POSITIVA = "positiva"                        # Com débitos
    POSITIVA_EFEITO_NEGATIVA = "positiva_efeito_negativa"  # Com débitos parcelados/sub judice
    INDISPONIVEL = "indisponivel"


class SituacaoDividaAtiva(str, Enum):
    SEM_DIVIDA = "sem_divida"
    EM_COBRANCA = "em_cobranca"
    PARCELADA = "parcelada"
    AJUIZADA = "ajuizada"
    SUSPENSA = "suspensa"
    DESCONHECIDA = "desconhecida"


# ── Models ───────────────────────────────────────────────────────────────────

class CNDStatus(BaseModel):
    """Certidão Negativa de Débitos relativos a Créditos Tributários Federais."""

    cnpj: str
    tipo_certidao: TipoCertidao = Field(TipoCertidao.INDISPONIVEL)
    codigo_certidao: Optional[str] = Field(None, description="Código de controle da certidão")
    data_emissao: Optional[datetime] = None
    data_validade: Optional[date] = None
    observacao: Optional[str] = None

    # Aptidão para contratar com governo
    apto_contratar_governo: bool = Field(
        False,
        description="Se CND ≠ positiva, pode contratar com governo",
    )

    fonte: str = Field("unknown")
    consultado_em: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_api_payload(cls, cnpj: str, payload: dict, *, fonte: str = "unknown") -> "CNDStatus":
        """Parse genérico de resposta de consulta CND."""
        tipo_raw = str(
            payload.get("tipo", payload.get("tipo_certidao", payload.get("type", "")))
        ).strip().lower()

        tipo_map = {
            "negativa": TipoCertidao.NEGATIVA,
            "positiva": TipoCertidao.POSITIVA,
            "positiva com efeito de negativa": TipoCertidao.POSITIVA_EFEITO_NEGATIVA,
            "positiva_efeito_negativa": TipoCertidao.POSITIVA_EFEITO_NEGATIVA,
        }
        tipo = tipo_map.get(tipo_raw, TipoCertidao.INDISPONIVEL)

        apto = tipo in (TipoCertidao.NEGATIVA, TipoCertidao.POSITIVA_EFEITO_NEGATIVA)

        return cls(
            cnpj="".join(filter(str.isdigit, cnpj)),
            tipo_certidao=tipo,
            codigo_certidao=payload.get("codigo", payload.get("code")),
            apto_contratar_governo=apto,
            fonte=fonte,
        )


class InscricaoDividaAtiva(BaseModel):
    """Uma inscrição individual em Dívida Ativa da União."""

    numero_inscricao: str = Field("", description="Número da inscrição DAU")
    valor_consolidado: float = Field(0.0, description="Valor consolidado (R$)")
    situacao: SituacaoDividaAtiva = Field(SituacaoDividaAtiva.DESCONHECIDA)
    tipo_devedor: Optional[str] = Field(None, description="Principal / Corresponsável")
    data_inscricao: Optional[date] = None
    indicador_ajuizado: bool = False


class DividaAtivaStatus(BaseModel):
    """Resumo de dívidas ativas do CNPJ junto à PGFN."""

    cnpj: str
    tem_divida: bool = False
    total_dividas: int = 0
    valor_total: float = Field(0.0, description="Soma de todas as inscrições (R$)")
    inscricoes: List[InscricaoDividaAtiva] = Field(default_factory=list)

    fonte: str = Field("unknown")
    consultado_em: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SituacaoFiscalMEI(BaseModel):
    """Consolidado da situação fiscal do MEI — CND + Dívida Ativa."""

    cnpj: str
    cnd: Optional[CNDStatus] = None
    divida_ativa: Optional[DividaAtivaStatus] = None

    # Indicadores calculados
    regular: bool = Field(False, description="Se está regular (sem pendências conhecidas)")
    pode_contratar_governo: bool = Field(False, description="Se pode participar de licitações")
    alertas: List[str] = Field(default_factory=list)

    def calcular_indicadores(self) -> None:
        """Calcula indicadores a partir dos dados de CND e Dívida Ativa."""
        self.alertas = []

        # CND
        if self.cnd:
            if self.cnd.tipo_certidao == TipoCertidao.NEGATIVA:
                self.pode_contratar_governo = True
            elif self.cnd.tipo_certidao == TipoCertidao.POSITIVA_EFEITO_NEGATIVA:
                self.pode_contratar_governo = True
                self.alertas.append(
                    "CND com efeito de negativa — há débitos parcelados ou em discussão judicial."
                )
            elif self.cnd.tipo_certidao == TipoCertidao.POSITIVA:
                self.pode_contratar_governo = False
                self.alertas.append(
                    "CND positiva — existem débitos pendentes com a União. "
                    "Regularize para participar de licitações."
                )
            else:
                self.alertas.append("CND indisponível — não foi possível consultar a Receita Federal.")

        # Dívida Ativa
        if self.divida_ativa and self.divida_ativa.tem_divida:
            self.pode_contratar_governo = False
            self.alertas.append(
                f"Dívida ativa: {self.divida_ativa.total_dividas} inscrição(ões) "
                f"totalizando R$ {self.divida_ativa.valor_total:,.2f}. "
                "Procure a PGFN para regularização."
            )

        # Regular se não tem alertas graves
        self.regular = self.pode_contratar_governo and (
            not self.divida_ativa or not self.divida_ativa.tem_divida
        )
