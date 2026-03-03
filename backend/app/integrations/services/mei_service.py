"""
Service — Diagnóstico MEI.

Orquestra múltiplos clients para fornecer um diagnóstico
consolidado do MEI: cadastro, obrigações, regularidade fiscal
e relacionamento com o governo.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List, Optional

from ..cnpj_client import CNPJClient, CNPJProvider, consultar_cnpj_com_fallback
from ..cnd_client import CNDClient
from ..divida_ativa_client import DividaAtivaClient
from ..transparencia_federal_client import TransparenciaFederalClient
from ..http_base import ExternalAPIError

from ..domain.mei_models import (
    AtividadeTipo,
    DiagnosticoMEI,
    MEIProfile,
    ObrigacoesMEI,
)
from ..domain.fiscal_models import SituacaoFiscalMEI

logger = logging.getLogger(__name__)


# ── Tabela DAS 2026 ─────────────────────────────────────────────────────────
# Base: Salário mínimo R$ 1.621,00 (5% INSS = R$ 81,05)
# ICMS fixo = R$ 1,00 | ISS fixo = R$ 5,00

_DAS_INSS_BASE = 81.05  # 5% do salário mínimo 2026

_DAS_COMPONENTES = {
    AtividadeTipo.COMERCIO: {
        "inss": _DAS_INSS_BASE,
        "icms": 1.00,
        "iss": 0.00,
        "total": 82.05,
    },
    AtividadeTipo.SERVICO: {
        "inss": _DAS_INSS_BASE,
        "icms": 0.00,
        "iss": 5.00,
        "total": 86.05,
    },
    AtividadeTipo.INDUSTRIA: {
        "inss": _DAS_INSS_BASE,
        "icms": 1.00,
        "iss": 0.00,
        "total": 82.05,
    },
    AtividadeTipo.MISTO: {
        "inss": _DAS_INSS_BASE,
        "icms": 1.00,
        "iss": 5.00,
        "total": 87.05,
    },
}


def _inferir_tipo_atividade(profile: MEIProfile) -> AtividadeTipo:
    """Infere tipo de atividade a partir do CNAE principal."""
    if not profile.cnae_principal:
        return AtividadeTipo.SERVICO

    codigo = profile.cnae_principal.codigo
    desc = (profile.cnae_principal.descricao or "").lower()

    # CNAE grupo 47xx = comércio varejista
    if codigo.startswith("47") or codigo.startswith("45") or codigo.startswith("46"):
        return AtividadeTipo.COMERCIO

    # CNAE grupo 10-33 = indústria
    try:
        divisao = int(codigo[:2])
        if 10 <= divisao <= 33:
            return AtividadeTipo.INDUSTRIA
    except (ValueError, IndexError):
        pass

    # Palavras-chave
    if any(w in desc for w in ["comércio", "comercio", "loja", "venda", "varejo"]):
        return AtividadeTipo.COMERCIO
    if any(w in desc for w in ["indústria", "industria", "fabricação", "fabricacao"]):
        return AtividadeTipo.INDUSTRIA

    return AtividadeTipo.SERVICO


def _proximo_vencimento_das() -> date:
    """Próximo dia 20 (vencimento padrão do DAS-MEI)."""
    hoje = date.today()
    # DAS vence no dia 20 do mês seguinte à competência
    if hoje.day <= 20:
        return hoje.replace(day=20)
    # Próximo mês
    if hoje.month == 12:
        return date(hoje.year + 1, 1, 20)
    return date(hoje.year, hoje.month + 1, 20)


def _calcular_obrigacoes(profile: MEIProfile) -> ObrigacoesMEI:
    """Calcula obrigações do MEI a partir do perfil."""
    tipo = _inferir_tipo_atividade(profile)
    profile.tipo_atividade = tipo

    componentes = _DAS_COMPONENTES.get(tipo, _DAS_COMPONENTES[AtividadeTipo.SERVICO])

    hoje = date.today()
    # DASN-SIMEI: vence 31/maio sobre o ano anterior
    dasn_ano = hoje.year - 1 if hoje.month >= 6 else hoje.year - 1
    dasn_prazo = date(hoje.year, 5, 31)

    return ObrigacoesMEI(
        cnpj=profile.cnpj,
        das_valor_mensal=componentes["total"],
        das_proximo_vencimento=_proximo_vencimento_das(),
        das_componentes=componentes,
        dasn_ano_referencia=dasn_ano,
        dasn_prazo=dasn_prazo,
        nfse_obrigatoria=tipo in (AtividadeTipo.SERVICO, AtividadeTipo.MISTO),
        nfse_emissor_nacional=True,  # 2026+ padrão
    )


class MEIService:
    """
    Service que orquestra o diagnóstico completo do MEI.

    Combina dados de:
    - Cadastro CNPJ (provedores com fallback)
    - CND (quando configurada)
    - Dívida Ativa (quando configurada)
    - Portal da Transparência (quando configurado)
    """

    def __init__(
        self,
        cnpj_provider: CNPJProvider = CNPJProvider.BRASILAPI,
    ):
        self.cnpj_provider = cnpj_provider

    async def diagnosticar_mei(
        self,
        cnpj: str,
        *,
        incluir_fiscal: bool = True,
        incluir_transparencia: bool = False,
        ano_transparencia: Optional[int] = None,
    ) -> DiagnosticoMEI:
        """
        Diagnóstico completo do MEI.

        Args:
            cnpj: CNPJ (com ou sem máscara)
            incluir_fiscal: Consultar CND + Dívida Ativa
            incluir_transparencia: Consultar Portal da Transparência
            ano_transparencia: Ano para dados de transparência

        Returns:
            DiagnosticoMEI com perfil, obrigações, alertas e recomendações
        """
        # 1. Cadastro CNPJ (com fallback)
        profile = await consultar_cnpj_com_fallback(cnpj)

        # 2. Obrigações
        obrigacoes = _calcular_obrigacoes(profile)

        # 3. Alertas e recomendações
        alertas: List[str] = []
        recomendacoes: List[str] = []

        if not profile.is_mei:
            alertas.append(
                "Este CNPJ NÃO está registrado como MEI (SIMEI). "
                "Se deveria ser, verifique no Portal do Empreendedor."
            )

        if profile.situacao_cadastral.value != "ativa":
            alertas.append(
                f"Situação cadastral: {profile.situacao_cadastral.value.upper()}. "
                "Regularize no Portal do Empreendedor."
            )

        if profile.is_mei and profile.data_abertura:
            anos_ativo = (date.today() - profile.data_abertura).days / 365
            if anos_ativo > 1:
                recomendacoes.append(
                    f"MEI ativo há {int(anos_ativo)} ano(s). "
                    "Verifique se o faturamento não ultrapassou R$ 81.000/ano."
                )

        # Obrigações
        recomendacoes.append(
            f"DAS mensal: R$ {obrigacoes.das_valor_mensal:.2f} "
            f"(próximo vencimento: {obrigacoes.das_proximo_vencimento})"
        )
        if obrigacoes.dasn_prazo:
            recomendacoes.append(
                f"DASN-SIMEI {obrigacoes.dasn_ano_referencia}: "
                f"prazo até {obrigacoes.dasn_prazo}"
            )
        if obrigacoes.nfse_obrigatoria:
            recomendacoes.append(
                "Emissão de NFSe é obrigatória para atividades de serviço. "
                "Use o Emissor Nacional NFS-e (padrão 2026+)."
            )

        # 4. Situação Fiscal (opcional)
        pagamentos_gov = 0
        valor_gov = 0.0

        if incluir_fiscal:
            fiscal = await self._consultar_fiscal(profile.cnpj)
            if fiscal:
                fiscal.calcular_indicadores()
                alertas.extend(fiscal.alertas)
                if not fiscal.pode_contratar_governo:
                    recomendacoes.append(
                        "Para participar de licitações, regularize "
                        "pendências com a Receita Federal e PGFN."
                    )

        # 5. Transparência (opcional)
        if incluir_transparencia:
            try:
                resumo = await self._consultar_transparencia(
                    profile.cnpj, ano=ano_transparencia
                )
                pagamentos_gov = resumo.total_pagamentos
                valor_gov = resumo.valor_total
                if pagamentos_gov > 0:
                    recomendacoes.append(
                        f"Você recebeu {pagamentos_gov} pagamento(s) "
                        f"do governo federal (R$ {valor_gov:,.2f}). "
                        "Explore novas oportunidades no ComprasGov."
                    )
            except Exception as e:
                logger.warning("Erro ao consultar transparência: %s", e)

        return DiagnosticoMEI(
            perfil=profile,
            obrigacoes=obrigacoes,
            alertas=alertas,
            recomendacoes=recomendacoes,
            pagamentos_governo_federal=pagamentos_gov,
            valor_total_governo=valor_gov,
        )

    async def consultar_perfil(self, cnpj: str) -> MEIProfile:
        """Consulta apenas o perfil do MEI (sem fiscal/transparência)."""
        return await consultar_cnpj_com_fallback(cnpj)

    async def _consultar_fiscal(self, cnpj: str) -> Optional[SituacaoFiscalMEI]:
        """Consulta CND + Dívida Ativa (ignora erros se não configurado)."""
        situacao = SituacaoFiscalMEI(cnpj=cnpj)

        try:
            async with CNDClient() as cnd_client:
                situacao.cnd = await cnd_client.consultar_cnd(cnpj)
        except Exception as e:
            logger.debug("CND não disponível: %s", e)

        try:
            async with DividaAtivaClient() as da_client:
                situacao.divida_ativa = await da_client.consultar(cnpj)
        except Exception as e:
            logger.debug("Dívida Ativa não disponível: %s", e)

        return situacao

    async def _consultar_transparencia(self, cnpj: str, ano: Optional[int] = None):
        """Consulta Portal da Transparência federal."""
        from ..transparencia_federal_client import TransparenciaFederalClient

        async with TransparenciaFederalClient() as client:
            return await client.resumo_pagamentos(cnpj, ano=ano)
