"""
Agente de Contabilidade MEI — NEXUS
====================================

Agente unificado que substitui os antigos agentes "Financeiro" e "Documentos".
Cobre TODAS as obrigações do Microempreendedor Individual (MEI) no Brasil,
com valores atualizados para 2026.

Obrigações cobertas:
 1. DAS-MEI mensal (vencimento dia 20)
 2. DASN-SIMEI (declaração anual, prazo 31/maio)
 3. NFS-e / NF-e (padrão nacional obrigatório desde 01/01/2026, CRT 4)
 4. Relatório Mensal de Receitas Brutas
 5. eSocial / FGTS Digital (se possui empregado)
 6. CCMEI / Licenças municipais
 7. IRPF Pessoa Física
 8. Guarda de documentos (5 anos)
 9. Desenquadramento / Excesso de receita
10. DTE-SN / e-CAC (caixa postal eletrônica)
11. Calendário fiscal completo
12. Checklist mensal/anual
13. Penalidades e multas
14. Controle de receitas, despesas e fluxo de caixa
15. Emissão de NFs, contratos e relatórios
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTES MEI 2026 (Salário Mínimo R$ 1.621,00)
# ============================================================================

SALARIO_MINIMO_2026 = 1621.00

# INSS MEI = 5% do salário mínimo
INSS_MEI_2026 = round(SALARIO_MINIMO_2026 * 0.05, 2)  # R$ 81.05

# Valores DAS por atividade (INSS + impostos fixos)
DAS_VALORES_2026 = {
    "comercio": round(INSS_MEI_2026 + 1.00, 2),            # R$ 82.05 (ICMS R$1)
    "industria": round(INSS_MEI_2026 + 1.00, 2),            # R$ 82.05 (ICMS R$1)
    "servicos": round(INSS_MEI_2026 + 5.00, 2),             # R$ 86.05 (ISS R$5)
    "comercio_servicos": round(INSS_MEI_2026 + 1.00 + 5.00, 2),  # R$ 87.05 (ICMS+ISS)
}

# MEI Caminhoneiro (INSS 12%)
INSS_CAMINHONEIRO_2026 = round(SALARIO_MINIMO_2026 * 0.12, 2)  # R$ 194.52
DAS_CAMINHONEIRO_2026 = {
    "municipal": round(INSS_CAMINHONEIRO_2026 + 5.00, 2),        # ~R$ 199.52
    "interestadual_intermunicipal": round(INSS_CAMINHONEIRO_2026 + 1.00, 2),  # ~R$ 195.52
    "ambos": round(INSS_CAMINHONEIRO_2026 + 6.00, 2),           # ~R$ 200.52
    "produtos_perigosos": round(INSS_CAMINHONEIRO_2026 + 1.00, 2),  # ~R$ 195.52
}

# Limites de faturamento
LIMITE_ANUAL_MEI = 81_000.00
LIMITE_MENSAL_IDEAL = round(LIMITE_ANUAL_MEI / 12, 2)  # R$ 6.750,00

# Tolerância para excesso (até 20% = R$ 97.200 paga sobre excesso)
LIMITE_EXCESSO_20_PERCENT = round(LIMITE_ANUAL_MEI * 1.20, 2)  # R$ 97.200,00

# Prazos fixos
DAS_VENCIMENTO_DIA = 20  # dia 20 de cada mês
DASN_PRAZO_MES = 5       # maio
DASN_PRAZO_DIA = 31      # 31 de maio

# IRPF — parcelas isentas por atividade
IRPF_LUCRO_ISENTO = {
    "comercio": 0.08,           # 8% comércio/indústria/transporte de carga
    "industria": 0.08,
    "transporte_carga": 0.08,
    "transporte_passageiros": 0.16,  # 16% transporte de passageiros
    "servicos": 0.32,           # 32% serviços em geral
}

# Multas e penalidades
MULTA_DAS_ATRASO_PERCENTUAL = 0.33   # 0,33% ao dia até 20%
MULTA_DAS_MAXIMO_PERCENTUAL = 0.20   # máximo 20%
JUROS_SELIC = True                    # juros = taxa Selic acumulada
MULTA_DASN_MINIMA = 50.00            # mínimo da multa por atraso DASN
MULTA_DASN_PERCENTUAL = 0.02         # 2% ao mês sobre tributos declarados
MULTA_DASN_MAXIMA_PERCENTUAL = 0.20  # máximo 20%

# Guarda de documentos
GUARDA_DOCUMENTOS_ANOS = 5


class TipoAtividade(str, Enum):
    COMERCIO = "comercio"
    INDUSTRIA = "industria"
    SERVICOS = "servicos"
    COMERCIO_SERVICOS = "comercio_servicos"


class ObrigacaoStatus(str, Enum):
    PENDENTE = "pendente"
    CONCLUIDA = "concluida"
    ATRASADA = "atrasada"
    NAO_APLICAVEL = "nao_aplicavel"


# ============================================================================
# AGENTE DE CONTABILIDADE
# ============================================================================

class ContabilidadeAgent:
    """
    Agente unificado de Contabilidade MEI.
    Substitui os antigos agentes 'Financeiro' e 'Documentos'.
    """

    def __init__(self):
        self.name = "contabilidade_agent"
        self.display_name = "📊 Contabilidade MEI"
        self.LIMITE_ANUAL_MEI = LIMITE_ANUAL_MEI
        self.LIMITE_MENSAL_IDEAL = LIMITE_MENSAL_IDEAL
        self.DAS_VALORES = DAS_VALORES_2026

    # ── Dispatcher principal ──────────────────────────────────────

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatcher central — roteia para o método correto."""
        action = parameters.get("action", "analyze_month")

        dispatch = {
            # Financeiro
            "analyze_month": self._analyze_month,
            "compare_months": self._compare_months,
            "forecast": self._forecast,
            "health_check": self._health_check,
            # DAS
            "das_status": self._das_status,
            "calcular_das": self._calcular_das,
            # DASN-SIMEI
            "dasn_status": self._dasn_status,
            # NFS-e / NF-e
            "prepare_invoice": self._prepare_invoice,
            "load_sales": self._load_sales,
            # Relatório Mensal de Receitas
            "relatorio_mensal": self._relatorio_mensal,
            # Limite MEI / Desenquadramento
            "mei_status": self._mei_status,
            "check_desenquadramento": self._check_desenquadramento,
            # eSocial
            "esocial_status": self._esocial_status,
            # CCMEI / Licenças
            "ccmei_status": self._ccmei_status,
            # IRPF
            "calcular_irpf_isento": self._calcular_irpf_isento,
            # Calendário
            "calendario_fiscal": self._calendario_fiscal,
            # Checklist
            "checklist_mensal": self._checklist_mensal,
            "checklist_anual": self._checklist_anual,
            # Penalidades
            "calcular_multa_das": self._calcular_multa_das,
            "consultar_penalidades": self._consultar_penalidades,
            # Guarda de documentos
            "guarda_documentos": self._guarda_documentos,
            # DTE-SN
            "dte_status": self._dte_status,
            # Contratos
            "generate_contract": self._generate_contract,
            "generate_report": self._generate_report,
        }

        handler = dispatch.get(action)
        if handler:
            return handler(parameters)
        return {
            "status": "error",
            "message": f"Ação desconhecida: {action}. Ações disponíveis: {list(dispatch.keys())}"
        }

    # ================================================================
    # 1. FINANCEIRO — Análise mensal
    # ================================================================

    def _analyze_month(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analisa financeiro de um mês."""

        month = parameters.get("month", datetime.now().strftime("%Y-%m"))
        tipo_atividade = parameters.get("tipo_atividade", "servicos")

        # Tentar dados do banco CRM
        receitas, despesas = self._get_financial_data_from_db(month)

        # Fallback: arquivo JSON
        if receitas == 0 and despesas == 0:
            file_data = self._load_financial_data(month)
            if file_data:
                receitas = sum(
                    item.get("valor", item.get("value", 0))
                    for item in file_data.get("receitas", file_data.get("revenues", []))
                )
                despesas = sum(
                    item.get("valor", item.get("value", 0))
                    for item in file_data.get("despesas", file_data.get("expenses", []))
                )

        # DAS
        das_valor = self.DAS_VALORES.get(tipo_atividade, self.DAS_VALORES["servicos"])
        total_impostos = das_valor

        # Cálculos
        total_receitas = round(receitas, 2)
        total_despesas = round(despesas, 2)
        lucro_liquido = round(total_receitas - total_despesas - total_impostos, 2)
        margem_lucro = round((lucro_liquido / total_receitas * 100), 1) if total_receitas > 0 else 0

        # Saúde financeira
        saude = self._calcular_saude_financeira(total_receitas, total_despesas, lucro_liquido, margem_lucro)

        # Limite MEI
        limite_check = self._check_limite_mei(total_receitas, month)

        # Insights
        insights = self._gerar_insights_mensais(total_receitas, total_despesas, lucro_liquido, margem_lucro, saude)
        recomendacoes = self._gerar_recomendacoes(total_receitas, total_despesas, lucro_liquido, margem_lucro, limite_check)

        return {
            "status": "analyzed",
            "mes": month,
            "tipo_atividade": tipo_atividade,
            "resumo": {
                "total_entrou": total_receitas,
                "total_saiu": total_despesas,
                "das_mensal": das_valor,
                "total_impostos": total_impostos,
                "lucro_liquido": lucro_liquido,
                "margem_lucro": margem_lucro,
                "saude_financeira": saude,
            },
            "limite_mei": limite_check,
            "insights": insights,
            "recomendacoes": recomendacoes,
            "explicacao": self._gerar_explicacao_simples(
                total_receitas, total_despesas, total_impostos, lucro_liquido, margem_lucro
            ),
        }

    def _compare_months(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Compara desempenho entre meses."""
        months = parameters.get("months", [])
        if len(months) < 2:
            return {"status": "error", "message": "Informe pelo menos 2 meses (ex: ['2025-12', '2026-01'])"}

        resultados = []
        for m in months:
            r = self._analyze_month({"month": m, **parameters})
            if r["status"] == "analyzed":
                resultados.append({"mes": m, "resumo": r["resumo"]})

        if len(resultados) < 2:
            return {"status": "error", "message": "Não foi possível analisar os meses solicitados"}

        atual = resultados[-1]
        anterior = resultados[-2]

        var_rec = atual["resumo"]["total_entrou"] - anterior["resumo"]["total_entrou"]
        var_luc = atual["resumo"]["lucro_liquido"] - anterior["resumo"]["lucro_liquido"]
        perc_rec = (var_rec / anterior["resumo"]["total_entrou"] * 100) if anterior["resumo"]["total_entrou"] > 0 else 0
        perc_luc = (var_luc / anterior["resumo"]["lucro_liquido"] * 100) if anterior["resumo"]["lucro_liquido"] > 0 else 0

        return {
            "status": "compared",
            "meses_analisados": months,
            "comparacao": {
                "mes_atual": atual,
                "mes_anterior": anterior,
                "variacoes": {
                    "receitas": {"valor": var_rec, "percentual": round(perc_rec, 1)},
                    "lucro": {"valor": var_luc, "percentual": round(perc_luc, 1)},
                },
            },
        }

    def _forecast(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Previsão de faturamento baseada em histórico."""
        historical_months = parameters.get("historical_months", 3)
        return {
            "status": "insufficient_data",
            "previsao_proximo_mes": {
                "receitas_estimadas": None,
                "confianca": "indisponível",
                "base": f"Últimos {historical_months} meses",
            },
            "message": "📊 Ainda não tenho dados suficientes para prever seu faturamento. Continue registrando suas movimentações!",
        }

    def _health_check(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Avalia saúde financeira geral (últimos 3 meses)."""
        hoje = datetime.now()
        resultados = []
        for i in range(3):
            mes = (hoje - timedelta(days=30 * i)).strftime("%Y-%m")
            r = self._analyze_month({"month": mes, **parameters})
            if r["status"] == "analyzed":
                resultados.append(r["resumo"])

        if not resultados:
            return {"status": "error", "message": "Sem dados para avaliar saúde financeira."}

        media_margem = sum(r["margem_lucro"] for r in resultados) / len(resultados)
        media_lucro = sum(r["lucro_liquido"] for r in resultados) / len(resultados)

        saude = (
            "Excelente ✅" if media_margem >= 30
            else "Boa 👍" if media_margem >= 20
            else "Atenção ⚠️" if media_margem >= 10
            else "Crítica 🚨"
        )

        return {
            "status": "checked",
            "saude_geral": saude,
            "medias_ultimos_3_meses": {
                "lucro": round(media_lucro, 2),
                "margem": round(media_margem, 1),
            },
        }

    # ================================================================
    # 2. DAS-MEI MENSAL
    # ================================================================

    def _das_status(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Status do próximo DAS: valor, vencimento, dias restantes."""
        tipo = parameters.get("tipo_atividade", "servicos")
        valor = self.DAS_VALORES.get(tipo, self.DAS_VALORES["servicos"])

        hoje = datetime.now()
        # Próximo vencimento: dia 20 do mês atual ou próximo
        if hoje.day <= DAS_VENCIMENTO_DIA:
            vencimento = hoje.replace(day=DAS_VENCIMENTO_DIA)
        else:
            # Próximo mês
            if hoje.month == 12:
                vencimento = hoje.replace(year=hoje.year + 1, month=1, day=DAS_VENCIMENTO_DIA)
            else:
                vencimento = hoje.replace(month=hoje.month + 1, day=DAS_VENCIMENTO_DIA)

        dias_restantes = (vencimento - hoje).days

        urgencia = (
            "🚨 VENCIDO" if dias_restantes < 0
            else "⚠️ URGENTE" if dias_restantes <= 3
            else "📅 PRÓXIMO" if dias_restantes <= 7
            else "✅ TRANQUILO"
        )

        return {
            "status": "ok",
            "das": {
                "valor": valor,
                "tipo_atividade": tipo,
                "composicao": {
                    "inss": INSS_MEI_2026,
                    "icms": 1.00 if tipo in ("comercio", "industria", "comercio_servicos") else 0,
                    "iss": 5.00 if tipo in ("servicos", "comercio_servicos") else 0,
                },
                "vencimento": vencimento.strftime("%d/%m/%Y"),
                "dias_restantes": dias_restantes,
                "urgencia": urgencia,
                "como_pagar": [
                    "Portal do Simples Nacional (PGMEI)",
                    "App MEI (Gov.br)",
                    "Débito automático",
                    "PIX (via DAS código de barras)",
                ],
            },
        }

    def _calcular_das(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Calcula DAS para determinado tipo de atividade."""
        tipo = parameters.get("tipo_atividade", "servicos")
        is_caminhoneiro = parameters.get("caminhoneiro", False)

        if is_caminhoneiro:
            subtipo = parameters.get("subtipo_caminhoneiro", "interestadual_intermunicipal")
            valor = DAS_CAMINHONEIRO_2026.get(subtipo, DAS_CAMINHONEIRO_2026["interestadual_intermunicipal"])
            return {
                "status": "ok",
                "tipo": "MEI Caminhoneiro",
                "subtipo": subtipo,
                "valor_das": valor,
                "composicao": {
                    "inss_12_percent": INSS_CAMINHONEIRO_2026,
                    "icms_iss": round(valor - INSS_CAMINHONEIRO_2026, 2),
                },
                "salario_minimo_base": SALARIO_MINIMO_2026,
            }

        valor = self.DAS_VALORES.get(tipo, self.DAS_VALORES["servicos"])
        return {
            "status": "ok",
            "tipo": tipo,
            "valor_das": valor,
            "composicao": {
                "inss_5_percent": INSS_MEI_2026,
                "icms": 1.00 if tipo in ("comercio", "industria", "comercio_servicos") else 0,
                "iss": 5.00 if tipo in ("servicos", "comercio_servicos") else 0,
            },
            "salario_minimo_base": SALARIO_MINIMO_2026,
        }

    # ================================================================
    # 3. DASN-SIMEI (Declaração Anual)
    # ================================================================

    def _dasn_status(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Status da DASN-SIMEI (declaração anual do MEI)."""
        ano_referencia = parameters.get("ano", datetime.now().year - 1)
        hoje = datetime.now()

        prazo = datetime(hoje.year, DASN_PRAZO_MES, DASN_PRAZO_DIA)
        dias_restantes = (prazo - hoje).days if hoje < prazo else -(hoje - prazo).days

        status = (
            "🚨 ATRASADA" if dias_restantes < 0
            else "⚠️ URGENTE" if dias_restantes <= 15
            else "📅 ATENÇÃO" if dias_restantes <= 30
            else "✅ NO PRAZO"
        )

        return {
            "status": "ok",
            "dasn": {
                "ano_referencia": ano_referencia,
                "prazo": prazo.strftime("%d/%m/%Y"),
                "dias_restantes": dias_restantes,
                "urgencia": status,
                "o_que_declarar": [
                    "Receita bruta total do ano",
                    "Informar se teve empregado",
                    "Receita de comércio/indústria separada de serviços",
                ],
                "onde_declarar": "Portal do Simples Nacional → DASN-SIMEI",
                "multa_atraso": {
                    "minima": MULTA_DASN_MINIMA,
                    "percentual_mes": f"{MULTA_DASN_PERCENTUAL*100}%",
                    "maximo": f"{MULTA_DASN_MAXIMA_PERCENTUAL*100}%",
                },
            },
        }

    # ================================================================
    # 4. NFS-e / NF-e
    # ================================================================

    def _prepare_invoice(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Prepara passos para emissão de NFS-e ou NF-e."""
        tipo_nf = parameters.get("tipo_nf", "nfse")
        cliente = parameters.get("cliente", parameters.get("client", ""))
        valor = parameters.get("valor", parameters.get("value", 0))
        descricao = parameters.get("descricao", parameters.get("description", ""))

        steps = []
        if tipo_nf == "nfse":
            steps = [
                "1. Acessar Portal Nacional NFS-e (nfse.gov.br) ou emissor municipal",
                "2. Login com certificado digital ou Gov.br",
                f"3. Preencher dados do tomador: {cliente or '[informar cliente]'}",
                f"4. Informar valor do serviço: R$ {valor:,.2f}" if valor else "4. Informar valor do serviço",
                f"5. Descrição do serviço: {descricao or '[informar descrição]'}",
                "6. Código CRT = 4 (obrigatório MEI desde 2026)",
                "7. Conferir dados e emitir",
                "8. Enviar PDF ao cliente por email",
            ]
        else:
            steps = [
                "1. Acessar emissor de NF-e (sistema estadual ou terceirizado)",
                "2. Login com certificado digital A1/A3",
                f"3. Dados do destinatário: {cliente or '[informar]'}",
                f"4. Produto e valor: R$ {valor:,.2f}" if valor else "4. Informar produtos e valores",
                "5. CFOP adequado para a operação",
                "6. CRT = 4 (obrigatório MEI desde 2026)",
                "7. Validar XML e transmitir",
                "8. Imprimir DANFE e enviar ao cliente",
            ]

        return {
            "status": "ok",
            "tipo": tipo_nf.upper(),
            "steps": steps,
            "observacoes": [
                "NFS-e padrão nacional obrigatório para MEI desde 01/01/2026",
                "CRT 4 obrigatório em todas as notas fiscais MEI",
                "Guardar XML e PDF por 5 anos",
            ],
        }

    def _load_sales(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Carrega dados de vendas de arquivo."""
        path = parameters.get("path", "data/sales.json")
        try:
            from agents import nf_agent as nf_module  # type: ignore[import-unresolved]
            data = nf_module.load_sales(path)
            return {"status": "ok", "data": data}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ================================================================
    # 5. RELATÓRIO MENSAL DE RECEITAS BRUTAS
    # ================================================================

    def _relatorio_mensal(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Gera relatório mensal de receitas brutas (obrigatório MEI)."""
        month = parameters.get("month", datetime.now().strftime("%Y-%m"))

        receitas, _ = self._get_financial_data_from_db(month)

        return {
            "status": "ok",
            "relatorio": {
                "mes_referencia": month,
                "receita_bruta_total": round(receitas, 2),
                "percentual_limite_mensal": round(receitas / LIMITE_MENSAL_IDEAL * 100, 1) if receitas > 0 else 0,
                "obrigacao": "Anexar NFs e documentos ao relatório",
                "prazo_preenchimento": "Até o dia 20 do mês seguinte",
                "modelo": "Relatório Mensal das Receitas Brutas (Anexo X da Resolução CGSN nº 140)",
            },
        }

    # ================================================================
    # 6. LIMITE MEI / DESENQUADRAMENTO
    # ================================================================

    def _mei_status(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Status completo do limite MEI."""
        month = parameters.get("month", datetime.now().strftime("%Y-%m"))
        receita_mensal, _ = self._get_financial_data_from_db(month)

        return self._check_limite_mei(receita_mensal, month)

    def _check_desenquadramento(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Verifica regras de desenquadramento do MEI."""
        receita_anual = parameters.get("receita_anual", 0)

        if receita_anual <= LIMITE_ANUAL_MEI:
            status = "✅ DENTRO DO LIMITE"
            acao = "Continue como MEI normalmente."
        elif receita_anual <= LIMITE_EXCESSO_20_PERCENT:
            status = "⚠️ EXCESSO ATÉ 20%"
            acao = (
                f"Receita excedeu o limite em R$ {receita_anual - LIMITE_ANUAL_MEI:,.2f}. "
                "Recolha DAS complementar sobre o excesso. "
                "Desenquadramento a partir de janeiro do ano seguinte."
            )
        else:
            status = "🚨 EXCESSO ACIMA DE 20%"
            acao = (
                f"Receita excedeu R$ {LIMITE_EXCESSO_20_PERCENT:,.2f}. "
                "Desenquadramento RETROATIVO ao início do ano. "
                "Recolher impostos como Simples Nacional ou Lucro Presumido. "
                "PROCURE UM CONTADOR IMEDIATAMENTE."
            )

        return {
            "status": "ok",
            "desenquadramento": {
                "receita_anual": receita_anual,
                "limite_mei": LIMITE_ANUAL_MEI,
                "limite_20_percent": LIMITE_EXCESSO_20_PERCENT,
                "situacao": status,
                "acao_necessaria": acao,
                "motivos_desenquadramento": [
                    "Faturamento acima de R$ 81.000/ano",
                    "Contratação de mais de 1 empregado",
                    "Inclusão de atividade não permitida ao MEI",
                    "Abertura de filial",
                    "Participação como sócio/administrador em outra empresa",
                ],
            },
        }

    # ================================================================
    # 7. eSocial / FGTS Digital
    # ================================================================

    def _esocial_status(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Status das obrigações eSocial (se tem empregado)."""
        tem_empregado = parameters.get("tem_empregado", False)

        if not tem_empregado:
            return {
                "status": "ok",
                "esocial": {
                    "aplicavel": False,
                    "message": "Sem empregado registrado. eSocial não é obrigatório.",
                },
            }

        salario_empregado = parameters.get("salario_empregado", SALARIO_MINIMO_2026)
        fgts_mensal = round(salario_empregado * 0.08, 2)
        inss_patronal = round(salario_empregado * 0.03, 2)  # 3% patronal MEI

        return {
            "status": "ok",
            "esocial": {
                "aplicavel": True,
                "empregado": {
                    "salario": salario_empregado,
                    "fgts_mensal": fgts_mensal,
                    "inss_patronal_3_percent": inss_patronal,
                    "custo_total_mensal": round(fgts_mensal + inss_patronal, 2),
                },
                "obrigacoes": [
                    "eSocial: eventos de admissão, folha mensal, férias, rescisão",
                    "FGTS Digital: recolhimento mensal até dia 20",
                    "GFIP/SEFIP: se aplicável",
                    "Folha de pagamento mensal",
                ],
                "prazos": {
                    "fgts": "Dia 20 de cada mês",
                    "esocial_mensal": "Dia 15 do mês seguinte",
                },
            },
        }

    # ================================================================
    # 8. CCMEI / Licenças
    # ================================================================

    def _ccmei_status(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Status do CCMEI e licenças municipais."""
        return {
            "status": "ok",
            "ccmei": {
                "o_que_e": "Certificado da Condição de Microempreendedor Individual",
                "validade": "Permanente (mas dados devem ser mantidos atualizados)",
                "como_emitir": "Portal do Empreendedor (gov.br/mei)",
                "atualizacoes_necessarias": [
                    "Mudança de endereço",
                    "Alteração de atividade (CNAE)",
                    "Mudança de nome fantasia",
                ],
            },
            "licencas": {
                "alvara_provisorio": "Emitido junto com CCMEI (automático)",
                "alvara_definitivo": "Verificar necessidade na prefeitura local",
                "vigilancia_sanitaria": "Obrigatório para alimentação, saúde, beleza",
                "corpo_bombeiros": "Obrigatório para ponto comercial (AVCB)",
                "licenca_ambiental": "Se atividade impacta meio ambiente",
            },
        }

    # ================================================================
    # 9. IRPF
    # ================================================================

    def _calcular_irpf_isento(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Calcula parcela isenta de IRPF para MEI."""
        receita_bruta_anual = parameters.get("receita_bruta_anual", 0)
        tipo = parameters.get("tipo_atividade", "servicos")
        despesas_comprovadas = parameters.get("despesas_comprovadas", 0)

        percentual_isento = IRPF_LUCRO_ISENTO.get(tipo, 0.32)
        lucro_isento = round(receita_bruta_anual * percentual_isento, 2)

        # Rendimento tributável = Receita - despesas - lucro isento - INSS pago
        inss_anual = INSS_MEI_2026 * 12
        rendimento_tributavel = max(
            0,
            receita_bruta_anual - despesas_comprovadas - lucro_isento - inss_anual
        )

        return {
            "status": "ok",
            "irpf": {
                "receita_bruta_anual": receita_bruta_anual,
                "tipo_atividade": tipo,
                "percentual_isento": f"{percentual_isento*100}%",
                "lucro_isento": lucro_isento,
                "inss_pago_anual": round(inss_anual, 2),
                "despesas_comprovadas": despesas_comprovadas,
                "rendimento_tributavel": round(rendimento_tributavel, 2),
                "observacoes": [
                    "Rendimento isento vai na ficha 'Rendimentos Isentos'",
                    "Rendimento tributável vai na ficha 'Rendimentos Tributáveis'",
                    "INSS pago (DAS) é dedutível",
                    f"Obrigatório declarar se rend. tributáveis > R$ 33.888 ou total > R$ 200.000",
                ],
            },
        }

    # ================================================================
    # 10. CALENDÁRIO FISCAL
    # ================================================================

    def _calendario_fiscal(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Retorna calendário fiscal completo do MEI."""
        ano = parameters.get("ano", datetime.now().year)

        calendario = {
            "mensal": {
                "dia_20": {
                    "obrigacao": "Pagamento DAS-MEI",
                    "descricao": "Guia única mensal (INSS + ICMS/ISS)",
                    "penalidade_atraso": "Multa 0,33%/dia + juros Selic",
                },
                "dia_20_fgts": {
                    "obrigacao": "FGTS Digital (se tem empregado)",
                    "descricao": "Recolhimento 8% sobre salário",
                },
                "continuo": {
                    "obrigacao": "Relatório Mensal de Receitas Brutas",
                    "descricao": "Preencher e anexar NFs ao relatório",
                },
            },
            "anual": {
                "31_maio": {
                    "obrigacao": "DASN-SIMEI",
                    "descricao": f"Declaração Anual do MEI — ano-base {ano - 1}",
                    "multa_atraso": f"Mínimo R$ {MULTA_DASN_MINIMA:.2f}",
                },
                "30_abril": {
                    "obrigacao": "IRPF (se obrigatório)",
                    "descricao": "Declaração de Imposto de Renda Pessoa Física",
                },
                "janeiro": {
                    "obrigacao": "NFS-e padrão nacional",
                    "descricao": "Obrigatório para todos os MEI desde 01/01/2026",
                },
            },
            "eventual": [
                "Atualização cadastral CCMEI (mudança de endereço/atividade)",
                "Renovação de licenças municipais (alvará, vigilância sanitária)",
                "Comunicação de desenquadramento (se ultrapassar limites)",
                "eSocial: admissão/demissão de empregado",
            ],
        }

        return {
            "status": "ok",
            "ano": ano,
            "calendario": calendario,
        }

    # ================================================================
    # 11. CHECKLIST MENSAL / ANUAL
    # ================================================================

    def _checklist_mensal(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Checklist mensal do MEI."""
        month = parameters.get("month", datetime.now().strftime("%Y-%m"))
        hoje = datetime.now()

        items = [
            {
                "item": "Pagar DAS até dia 20",
                "status": "concluido" if hoje.day > DAS_VENCIMENTO_DIA else "pendente",
                "prioridade": "alta",
                "valor": self.DAS_VALORES.get(
                    parameters.get("tipo_atividade", "servicos"),
                    self.DAS_VALORES["servicos"]
                ),
            },
            {
                "item": "Preencher Relatório Mensal de Receitas Brutas",
                "status": "pendente",
                "prioridade": "média",
            },
            {
                "item": "Emitir NFS-e para todos os serviços prestados",
                "status": "pendente",
                "prioridade": "alta",
            },
            {
                "item": "Verificar se há NFs de compra para guardar",
                "status": "pendente",
                "prioridade": "baixa",
            },
            {
                "item": "Verificar caixa postal DTE-SN/e-CAC",
                "status": "pendente",
                "prioridade": "média",
            },
            {
                "item": "Conferir extrato bancário x receitas",
                "status": "pendente",
                "prioridade": "média",
            },
        ]

        # Se tem empregado, adicionar itens
        if parameters.get("tem_empregado", False):
            items.extend([
                {
                    "item": "Recolher FGTS Digital até dia 20",
                    "status": "pendente",
                    "prioridade": "alta",
                },
                {
                    "item": "Enviar eSocial mensal até dia 15",
                    "status": "pendente",
                    "prioridade": "alta",
                },
            ])

        return {
            "status": "ok",
            "mes": month,
            "checklist": items,
            "total_pendentes": sum(1 for i in items if i["status"] == "pendente"),
        }

    def _checklist_anual(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Checklist anual do MEI."""
        ano = parameters.get("ano", datetime.now().year)

        items = [
            {
                "item": f"Entregar DASN-SIMEI (ano-base {ano - 1})",
                "prazo": f"31/05/{ano}",
                "prioridade": "alta",
            },
            {
                "item": "Declarar IRPF (se obrigatório)",
                "prazo": f"30/04/{ano}",
                "prioridade": "alta",
            },
            {
                "item": "Verificar se atingiu limite de R$ 81.000",
                "prazo": f"31/12/{ano}",
                "prioridade": "alta",
            },
            {
                "item": "Renovar licenças municipais (alvará, AVCB, sanitária)",
                "prazo": "Conforme prefeitura",
                "prioridade": "média",
            },
            {
                "item": "Atualizar CCMEI se houve mudança cadastral",
                "prazo": "Imediato após mudança",
                "prioridade": "média",
            },
            {
                "item": "Revisar atividades CNAE — verificar se continua como MEI",
                "prazo": "Anual",
                "prioridade": "baixa",
            },
            {
                "item": "Organizar documentos do ano para guarda de 5 anos",
                "prazo": f"Janeiro/{ano + 1}",
                "prioridade": "média",
            },
        ]

        return {
            "status": "ok",
            "ano": ano,
            "checklist": items,
        }

    # ================================================================
    # 12. PENALIDADES E MULTAS
    # ================================================================

    def _calcular_multa_das(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Calcula multa e juros por DAS em atraso."""
        valor_das = parameters.get("valor_das", self.DAS_VALORES["servicos"])
        dias_atraso = parameters.get("dias_atraso", 0)

        if dias_atraso <= 0:
            return {"status": "ok", "multa": 0, "juros": 0, "total": valor_das, "message": "DAS em dia ✅"}

        # Multa: 0,33% ao dia, máximo 20%
        percentual_multa = min(dias_atraso * MULTA_DAS_ATRASO_PERCENTUAL / 100, MULTA_DAS_MAXIMO_PERCENTUAL)
        multa = round(valor_das * percentual_multa, 2)

        # Juros: Selic acumulada (simplificado: ~1% ao mês)
        meses_atraso = max(1, dias_atraso // 30)
        juros = round(valor_das * 0.01 * meses_atraso, 2)

        total = round(valor_das + multa + juros, 2)

        return {
            "status": "ok",
            "das_original": valor_das,
            "dias_atraso": dias_atraso,
            "multa": multa,
            "percentual_multa": f"{percentual_multa * 100:.1f}%",
            "juros_estimados": juros,
            "total_a_pagar": total,
            "observacao": "Juros baseados em estimativa. Valor exato depende da Selic acumulada.",
        }

    def _consultar_penalidades(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Lista todas as penalidades possíveis para MEI."""
        return {
            "status": "ok",
            "penalidades": [
                {
                    "tipo": "DAS em atraso",
                    "multa": "0,33% ao dia (máx 20%) + Selic",
                    "consequencia": "Dívida ativa, perde benefícios INSS após 12 meses",
                },
                {
                    "tipo": "DASN-SIMEI em atraso",
                    "multa": f"2% ao mês (mín R$ {MULTA_DASN_MINIMA}, máx 20%)",
                    "consequencia": "Não gera DAS do ano seguinte, risco de cancelamento CNPJ",
                },
                {
                    "tipo": "Não emitir NF quando obrigatório",
                    "multa": "Depende da legislação municipal/estadual",
                    "consequencia": "Autuação fiscal, pode levar a desenquadramento",
                },
                {
                    "tipo": "CNPJ inapto (DAS > 12 meses)",
                    "multa": "Cancelamento do CNPJ após notificação",
                    "consequencia": "Perda de todos os benefícios MEI e INSS",
                },
                {
                    "tipo": "Excesso de faturamento sem comunicação",
                    "multa": "Recolhimento retroativo dos impostos + multa",
                    "consequencia": "Desenquadramento retroativo ou prospectivo",
                },
            ],
        }

    # ================================================================
    # 13. GUARDA DE DOCUMENTOS
    # ================================================================

    def _guarda_documentos(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Orientações sobre guarda de documentos."""
        return {
            "status": "ok",
            "guarda": {
                "prazo_geral": f"{GUARDA_DOCUMENTOS_ANOS} anos",
                "documentos_obrigatorios": [
                    "Notas Fiscais emitidas e recebidas (XML e PDF)",
                    "Comprovantes de pagamento do DAS",
                    "Relatórios Mensais de Receitas Brutas",
                    "DASN-SIMEI (recibo de entrega)",
                    "Extratos bancários da conta PJ",
                    "Contratos de prestação de serviço",
                    "Alvará e licenças municipais",
                    "CCMEI atualizado",
                ],
                "dicas": [
                    "Digitalize todos os documentos físicos",
                    "Mantenha backup em nuvem (Google Drive, OneDrive)",
                    "Organize por ano e mês",
                    "O NEXUS guarda automaticamente registros digitais 📁",
                ],
            },
        }

    # ================================================================
    # 14. DTE-SN / e-CAC
    # ================================================================

    def _dte_status(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Orientações sobre DTE-SN (caixa postal eletrônica)."""
        return {
            "status": "ok",
            "dte": {
                "o_que_e": "Domicílio Tributário Eletrônico do Simples Nacional",
                "importancia": "Notificações fiscais são enviadas por aqui — tem validade legal",
                "como_acessar": [
                    "Portal do Simples Nacional → DTE-SN",
                    "e-CAC da Receita Federal (Gov.br nível prata/ouro)",
                ],
                "frequencia_verificacao": "Pelo menos quinzenalmente",
                "risco_nao_verificar": "Notificação não lida = ciência automática após 45 dias",
            },
        }

    # ================================================================
    # 15. CONTRATOS E RELATÓRIOS
    # ================================================================

    def _generate_contract(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Gera modelo de contrato."""
        tipo = parameters.get("tipo", "servico")
        templates = {
            "servico": "Contrato de Prestação de Serviço",
            "produto": "Contrato de Compra e Venda",
            "consultoria": "Contrato de Consultoria",
        }
        return {
            "status": "ok",
            "contrato": {
                "tipo": templates.get(tipo, tipo),
                "message": f"Modelo de {templates.get(tipo, tipo)} pronto para personalizar.",
                "campos_necessarios": [
                    "Nome/razão social das partes",
                    "CPF/CNPJ",
                    "Objeto do contrato",
                    "Valor e condições de pagamento",
                    "Prazo de vigência",
                    "Responsabilidades de cada parte",
                ],
            },
        }

    def _generate_report(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Lista relatórios disponíveis."""
        return {
            "status": "ok",
            "relatorios_disponiveis": [
                {"id": "financeiro_mensal", "nome": "Resumo Financeiro Mensal", "descricao": "Receitas x Despesas x Lucro"},
                {"id": "receitas_brutas", "nome": "Relatório de Receitas Brutas", "descricao": "Obrigatório MEI — anexar NFs"},
                {"id": "limite_mei", "nome": "Acompanhamento Limite MEI", "descricao": "% utilizado + projeção anual"},
                {"id": "das_historico", "nome": "Histórico DAS", "descricao": "Pagamentos DAS dos últimos 12 meses"},
                {"id": "clientes", "nome": "Relatório de Clientes", "descricao": "Top clientes por faturamento"},
                {"id": "pipeline", "nome": "Pipeline de Vendas", "descricao": "Oportunidades por estágio"},
            ],
        }

    # ================================================================
    # HELPERS
    # ================================================================

    def _get_financial_data_from_db(self, month: str) -> tuple[float, float]:
        """Busca receitas e despesas do CRM/banco de dados."""
        try:
            from database.crm_service import CRMService  # type: ignore[import-unresolved]
            parts = month.split("-")
            m, y = int(parts[1]), int(parts[0])
            summary = CRMService.get_financial_summary(month=m, year=y)
            return summary.get("receitas", 0), summary.get("despesas", 0)
        except Exception:
            return 0, 0

    def _calcular_saude_financeira(self, receitas: float, despesas: float, lucro: float, margem: float) -> str:
        if lucro <= 0:
            return "🚨 Prejuízo"
        elif margem >= 40:
            return "✅ Excelente"
        elif margem >= 25:
            return "👍 Muito Boa"
        elif margem >= 15:
            return "😊 Boa"
        elif margem >= 5:
            return "⚠️ Atenção"
        return "🔴 Crítica"

    def _check_limite_mei(self, receita_mensal: float, month: str) -> Dict[str, Any]:
        mes_numero = int(month.split("-")[1])
        faturamento_acumulado = receita_mensal * mes_numero
        percentual = (faturamento_acumulado / self.LIMITE_ANUAL_MEI * 100) if self.LIMITE_ANUAL_MEI > 0 else 0

        if percentual >= 100:
            status = "🚨 ULTRAPASSADO"
            alerta = "ATENÇÃO! Limite MEI ultrapassado. Procure um contador para regularizar."
        elif percentual >= 80:
            status = "⚠️ ATENÇÃO"
            alerta = f"Já usou {percentual:.1f}% do limite anual. Cuidado para não ultrapassar!"
        elif percentual >= 60:
            status = "😊 MONITORANDO"
            alerta = f"Usando {percentual:.1f}% do limite. Continue monitorando."
        else:
            status = "✅ TRANQUILO"
            alerta = f"Apenas {percentual:.1f}% do limite anual. Tudo certo!"

        return {
            "status": status,
            "percentual_usado": round(percentual, 1),
            "limite_anual": self.LIMITE_ANUAL_MEI,
            "faturamento_acumulado_estimado": round(faturamento_acumulado, 2),
            "limite_restante": max(0, round(self.LIMITE_ANUAL_MEI - faturamento_acumulado, 2)),
            "alerta": alerta,
        }

    def _gerar_insights_mensais(self, rec: float, desp: float, lucro: float, margem: float, saude: str) -> List[str]:
        insights = []
        if lucro > 0:
            insights.append(f"💚 Lucro de R$ {lucro:.2f} no mês. Parabéns!")
        else:
            insights.append(f"🔴 Prejuízo de R$ {abs(lucro):.2f}. Precisamos ajustar.")

        if margem >= 30:
            insights.append(f"🎯 Margem excelente ({margem:.1f}%).")
        elif margem >= 15:
            insights.append(f"👍 Margem razoável ({margem:.1f}%). Dá pra melhorar.")
        elif margem > 0:
            insights.append(f"⚠️ Margem baixa ({margem:.1f}%). Revise preços e custos.")

        if rec > 0 and desp / rec > 0.70:
            insights.append(f"🚨 Despesas muito altas ({desp/rec*100:.0f}% da receita).")

        if rec < self.LIMITE_MENSAL_IDEAL * 0.5:
            insights.append(f"📊 Espaço para crescer: pode faturar até R$ {self.LIMITE_MENSAL_IDEAL:,.2f}/mês.")

        return insights

    def _gerar_recomendacoes(self, rec: float, desp: float, lucro: float, margem: float, limite: Dict) -> List[str]:
        recs = []
        if margem < 15:
            recs.append("💡 Revise seus preços — margem muito baixa.")
        if lucro < 0:
            recs.append("🚨 URGENTE: Reduza despesas ou aumente vendas.")
        if limite.get("percentual_usado", 0) >= 80:
            recs.append("⚠️ Procure um contador. Pode precisar migrar para Simples Nacional.")
        if not recs:
            recs.append("✅ Continue assim! Negócio saudável.")
            recs.append("💰 Guarde parte do lucro para emergências.")
        return recs

    def _gerar_explicacao_simples(self, rec: float, desp: float, imp: float, lucro: float, margem: float) -> str:
        return (
            f"📊 RESUMO DO MÊS\n"
            f"💵 Entrou: R$ {rec:,.2f}\n"
            f"💸 Saiu: R$ {desp:,.2f} + DAS R$ {imp:,.2f}\n"
            f"{'💚' if lucro > 0 else '🔴'} Lucro: R$ {lucro:,.2f}\n"
            f"📈 Margem: {margem:.1f}%"
        )

    def _load_financial_data(self, month: str) -> Optional[Dict[str, Any]]:
        data_file = Path("data") / "mei_finances_example.json"
        if not data_file.exists():
            return None
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                all_data = json.load(f)
            if isinstance(all_data, dict) and month in all_data:
                return all_data[month]
            if isinstance(all_data, list):
                for item in all_data:
                    if item.get("month") == month:
                        return item
            return None
        except Exception as e:
            logger.warning(f"Erro ao carregar dados financeiros: {e}")
            return None


# ============================================================================
# HELPER PÚBLICO
# ============================================================================

def run_contabilidade_agent(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Helper para executar o agente de contabilidade."""
    agent = ContabilidadeAgent()
    return agent.execute(parameters)
