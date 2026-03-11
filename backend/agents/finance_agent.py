"""
Agente de Análise Financeira para MEI
======================================

⚠️ NOTA DE DEPRECAÇÃO (MEDIUM FIX #12):
A maioria das funcionalidades deste módulo foi migrada para
`backend/agents/contabilidade_agent.py` (1156 linhas), que é o
agente principal de contabilidade e finanças.

Este módulo é mantido como BIBLIOTECA INTERNA para:
- forecast() — previsão financeira com dados reais (reimplementado)
- _analyze_month() — análise mensal detalhada
- _compare_months() — comparação entre meses
- _health_check() — saúde financeira

Para novos desenvolvimentos, use ContabilidadeAgent.

Análise financeira completa e descomplicada para microempreendedores.
Linguagem simples, insights práticos, sem jargões técnicos.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FinanceAgent:
    """
    Agente de Análise Financeira - Seu Contador Pessoal
    
    Funcionalidades:
    - Análise mensal de entradas e saídas
    - Cálculo de lucro real
    - Alertas de impostos (DAS)
    - Comparação com meses anteriores
    - Previsão de faturamento
    - Recomendações práticas
    - Relatórios em linguagem clara
    """
    
    def __init__(self):
        self.name = "finance_agent"
        self.display_name = "💰 Análise Financeira"
        
        # Limites MEI (2026)
        self.LIMITE_ANUAL_MEI = 81000.00  # R$ 81.000/ano
        self.LIMITE_MENSAL_IDEAL = 6750.00  # R$ 6.750/mês (81k/12)
        
        # DAS valores 2026 — baseado no salário mínimo R$ 1.621,00
        # INSS MEI = 5% de R$ 1.621 = R$ 81,05
        self.SALARIO_MINIMO = 1621.00
        self.INSS_MEI = round(self.SALARIO_MINIMO * 0.05, 2)  # R$ 81,05
        self.DAS_VALORES = {
            "comercio": round(self.INSS_MEI + 1.00, 2),            # R$ 82,05 (ICMS R$1)
            "industria": round(self.INSS_MEI + 1.00, 2),            # R$ 82,05 (ICMS R$1)
            "servicos": round(self.INSS_MEI + 5.00, 2),             # R$ 86,05 (ISS R$5)
            "comercio_servicos": round(self.INSS_MEI + 6.00, 2),    # R$ 87,05 (ICMS+ISS)
        }
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa análise financeira.
        
        Parâmetros:
            - action: tipo de análise
                • analyze_month: analisa um mês específico
                • compare_months: compara dois ou mais meses
                • forecast: faz previsão baseada no histórico
                • health_check: avalia saúde financeira geral
            
            # Dados financeiros
            - month: mês a analisar (YYYY-MM)
            - receitas: lista de receitas [{"descricao": "Venda X", "valor": 1500, "data": "2026-01-15"}]
            - despesas: lista de despesas [{"descricao": "Aluguel", "valor": 800, "data": "2026-01-05"}]
            - impostos_pagos: valor de impostos já pagos no mês
            
            # Para comparação
            - months: lista de meses para comparar
            - financial_data: dados de múltiplos meses
            
            # Para previsão
            - historical_months: número de meses históricos para base
        """
        try:
            action = parameters.get("action", "analyze_month")
            
            if action == "analyze_month":
                return self._analyze_month(parameters)
            elif action == "compare_months":
                return self._compare_months(parameters)
            elif action == "forecast":
                return self._forecast(parameters)
            elif action == "health_check":
                return self._health_check(parameters)
            else:
                return {
                    "status": "error",
                    "message": f"Ação desconhecida: {action}"
                }
                
        except Exception as e:
            logger.exception(f"Erro no finance_agent: {e}")
            return {
                "status": "error",
                "message": f"Erro ao analisar: {e}"
            }
    
    def _analyze_month(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analisa financeiro de um mês específico."""
        
        month = parameters.get("month")
        if not month:
            return {
                "status": "error",
                "message": "Informe o mês (formato: YYYY-MM, ex: 2026-01)"
            }
        
        # Obter dados financeiros
        receitas = parameters.get("receitas", [])
        despesas = parameters.get("despesas", [])
        impostos_pagos = parameters.get("impostos_pagos", 0.0)
        categoria_mei = parameters.get("categoria_mei", "servicos")
        
        # Se não tiver dados, tentar carregar de arquivo
        if not receitas and not despesas:
            financial_data = self._load_financial_data(month)
            if financial_data:
                receitas = financial_data.get("receitas", [])
                despesas = financial_data.get("despesas", [])
                impostos_pagos = financial_data.get("impostos_pagos", 0.0)
        
        # Calcular totais
        total_receitas = sum(float(r.get("valor", 0)) for r in receitas)
        total_despesas = sum(float(d.get("valor", 0)) for d in despesas)
        
        # DAS do mês
        das_mes = self.DAS_VALORES.get(categoria_mei, 76.00)
        
        # Impostos totais (DAS + outros)
        total_impostos = das_mes + impostos_pagos
        
        # Lucro líquido = Receitas - Despesas - Impostos
        lucro_liquido = total_receitas - total_despesas - total_impostos
        
        # Margem de lucro (% que sobra do que você ganha)
        margem_lucro = (lucro_liquido / total_receitas * 100) if total_receitas > 0 else 0
        
        # Análise de saúde
        saude = self._calcular_saude_financeira(
            total_receitas, 
            total_despesas, 
            lucro_liquido, 
            margem_lucro
        )
        
        # Verificar limite MEI
        limite_check = self._check_limite_mei(total_receitas, month)
        
        # Gerar insights
        insights = self._gerar_insights_mensais(
            total_receitas,
            total_despesas,
            lucro_liquido,
            margem_lucro,
            saude
        )
        
        # Recomendações práticas
        recomendacoes = self._gerar_recomendacoes(
            total_receitas,
            total_despesas,
            lucro_liquido,
            margem_lucro,
            limite_check
        )
        
        # Maiores receitas e despesas
        top_receitas = sorted(receitas, key=lambda x: float(x.get("valor", 0)), reverse=True)[:3]
        top_despesas = sorted(despesas, key=lambda x: float(x.get("valor", 0)), reverse=True)[:3]
        
        return {
            "status": "analyzed",
            "month": month,
            "resumo": {
                "total_entrou": total_receitas,
                "total_saiu": total_despesas,
                "impostos": total_impostos,
                "das_mes": das_mes,
                "lucro_liquido": lucro_liquido,
                "margem_lucro": round(margem_lucro, 1),
                "saude_financeira": saude
            },
            "detalhes": {
                "quantidade_vendas": len(receitas),
                "ticket_medio": round(total_receitas / len(receitas), 2) if receitas else 0,
                "quantidade_despesas": len(despesas),
                "despesa_media": round(total_despesas / len(despesas), 2) if despesas else 0,
                "top_receitas": top_receitas,
                "top_despesas": top_despesas
            },
            "limite_mei": limite_check,
            "insights": insights,
            "recomendacoes": recomendacoes,
            "explicacao": self._gerar_explicacao_simples(
                total_receitas,
                total_despesas,
                total_impostos,
                lucro_liquido,
                margem_lucro
            )
        }
    
    def _compare_months(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Compara desempenho entre meses."""
        
        months = parameters.get("months", [])
        if len(months) < 2:
            return {
                "status": "error",
                "message": "Informe pelo menos 2 meses para comparar (ex: ['2025-12', '2026-01'])"
            }
        
        # Analisar cada mês
        resultados_meses = []
        for month in months:
            result = self._analyze_month({"month": month, **parameters})
            if result["status"] == "analyzed":
                resultados_meses.append({
                    "mes": month,
                    "resumo": result["resumo"]
                })
        
        if len(resultados_meses) < 2:
            return {
                "status": "error",
                "message": "Não foi possível analisar os meses solicitados"
            }
        
        # Comparar último mês com penúltimo
        mes_atual = resultados_meses[-1]
        mes_anterior = resultados_meses[-2]
        
        # Calcular variações
        variacao_receitas = mes_atual["resumo"]["total_entrou"] - mes_anterior["resumo"]["total_entrou"]
        variacao_despesas = mes_atual["resumo"]["total_saiu"] - mes_anterior["resumo"]["total_saiu"]
        variacao_lucro = mes_atual["resumo"]["lucro_liquido"] - mes_anterior["resumo"]["lucro_liquido"]
        
        # Percentuais
        perc_receitas = (variacao_receitas / mes_anterior["resumo"]["total_entrou"] * 100) if mes_anterior["resumo"]["total_entrou"] > 0 else 0
        perc_despesas = (variacao_despesas / mes_anterior["resumo"]["total_saiu"] * 100) if mes_anterior["resumo"]["total_saiu"] > 0 else 0
        perc_lucro = (variacao_lucro / mes_anterior["resumo"]["lucro_liquido"] * 100) if mes_anterior["resumo"]["lucro_liquido"] > 0 else 0
        
        # Análise de tendência
        tendencia = self._analisar_tendencia(resultados_meses)
        
        return {
            "status": "compared",
            "meses_analisados": months,
            "comparacao": {
                "mes_atual": mes_atual,
                "mes_anterior": mes_anterior,
                "variacoes": {
                    "receitas": {
                        "valor": variacao_receitas,
                        "percentual": round(perc_receitas, 1),
                        "status": "subiu" if variacao_receitas > 0 else "desceu" if variacao_receitas < 0 else "estável"
                    },
                    "despesas": {
                        "valor": variacao_despesas,
                        "percentual": round(perc_despesas, 1),
                        "status": "subiu" if variacao_despesas > 0 else "desceu" if variacao_despesas < 0 else "estável"
                    },
                    "lucro": {
                        "valor": variacao_lucro,
                        "percentual": round(perc_lucro, 1),
                        "status": "melhorou" if variacao_lucro > 0 else "piorou" if variacao_lucro < 0 else "estável"
                    }
                }
            },
            "tendencia": tendencia,
            "explicacao": self._gerar_explicacao_comparacao(
                mes_atual,
                mes_anterior,
                variacao_receitas,
                variacao_lucro,
                perc_receitas,
                perc_lucro
            )
        }
    
    def _forecast(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Faz previsão de faturamento baseada no histórico real de transações.
        HIGH FIX #8: Implementação real de forecast (era STUB)."""

        historical_months = parameters.get("historical_months", 3)
        user_id = parameters.get("user_id")

        # Buscar dados reais dos últimos N meses via CRMService
        try:
            from database.crm_service import CRMService
        except ImportError:
            CRMService = None

        monthly_data: List[Dict[str, Any]] = []
        hoje = datetime.now()

        for i in range(historical_months):
            target = hoje - timedelta(days=30 * i)
            m, y = target.month, target.year
            if CRMService:
                summary = CRMService.get_financial_summary(month=m, year=y, user_id=user_id)
            else:
                summary = {"receitas": 0, "despesas": 0, "lucro": 0, "transactions_count": 0}
            if summary.get("transactions_count", 0) > 0:
                monthly_data.append({
                    "month": f"{y}-{m:02d}",
                    "receitas": summary.get("receitas", 0),
                    "despesas": summary.get("despesas", 0),
                    "lucro": summary.get("lucro", 0),
                })

        if len(monthly_data) < 1:
            return {
                "status": "insufficient_data",
                "previsao_proximo_mes": {
                    "receitas_estimadas": None,
                    "confianca": "indisponível",
                    "base": f"Últimos {historical_months} meses"
                },
                "message": "📊 Ainda não tenho dados suficientes para fazer uma previsão confiável. "
                           "Continue registrando suas vendas e despesas que em breve poderei te ajudar com projeções!"
            }

        # Média móvel simples (SMA) para previsão
        receitas = [d["receitas"] for d in monthly_data]
        despesas = [d["despesas"] for d in monthly_data]

        media_receitas = sum(receitas) / len(receitas)
        media_despesas = sum(despesas) / len(despesas)
        media_lucro = media_receitas - media_despesas

        # Tendência: comparar primeiro e último mês se >= 2 meses
        tendencia = "estável"
        variacao_pct = 0.0
        if len(receitas) >= 2:
            mais_recente = receitas[0]
            mais_antigo = receitas[-1]
            if mais_antigo > 0:
                variacao_pct = ((mais_recente - mais_antigo) / mais_antigo) * 100
                if variacao_pct > 5:
                    tendencia = "crescente 📈"
                elif variacao_pct < -5:
                    tendencia = "decrescente 📉"
                else:
                    tendencia = "estável ➡️"

        # Confiança baseada na quantidade de dados
        if len(monthly_data) >= 3:
            confianca = "média"
        elif len(monthly_data) == 2:
            confianca = "baixa"
        else:
            confianca = "muito baixa (apenas 1 mês)"

        # Projeção = média com ajuste de tendência
        ajuste = 1 + (variacao_pct / 100 * 0.5) if variacao_pct else 1.0
        receitas_estimadas = round(media_receitas * ajuste, 2)
        despesas_estimadas = round(media_despesas, 2)
        lucro_estimado = round(receitas_estimadas - despesas_estimadas, 2)

        # Limite MEI
        receita_acumulada_ano = sum(receitas)  # simplificação: meses carregados
        projecao_anual = round(receitas_estimadas * 12, 2)
        alerta_mei = projecao_anual > self.LIMITE_ANUAL_MEI

        return {
            "status": "forecast_ready",
            "previsao_proximo_mes": {
                "receitas_estimadas": receitas_estimadas,
                "despesas_estimadas": despesas_estimadas,
                "lucro_estimado": lucro_estimado,
                "confianca": confianca,
                "tendencia": tendencia,
                "variacao_pct": round(variacao_pct, 1),
                "base": f"Últimos {len(monthly_data)} meses",
            },
            "historico_utilizado": monthly_data,
            "projecao_anual": projecao_anual,
            "alerta_limite_mei": alerta_mei,
            "message": (
                f"📊 **Previsão para o próximo mês**\n\n"
                f"💰 Receitas estimadas: R$ {receitas_estimadas:,.2f}\n"
                f"💸 Despesas estimadas: R$ {despesas_estimadas:,.2f}\n"
                f"📈 Lucro estimado: R$ {lucro_estimado:,.2f}\n"
                f"📉 Tendência: {tendencia} ({variacao_pct:+.1f}%)\n"
                f"🔮 Confiança: {confianca}\n\n"
                f"Baseado nos últimos {len(monthly_data)} meses."
                + (f"\n\n⚠️ **ALERTA MEI**: Projeção anual R$ {projecao_anual:,.2f} ultrapassa "
                   f"o limite de R$ {self.LIMITE_ANUAL_MEI:,.2f}!" if alerta_mei else "")
            ),
        }
    
    def _health_check(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Avalia saúde financeira geral."""
        
        # Buscar dados dos últimos 3 meses
        hoje = datetime.now()
        meses = []
        for i in range(3):
            mes = (hoje - timedelta(days=30 * i)).strftime("%Y-%m")
            meses.append(mes)
        
        # Analisar cada mês
        resultados = []
        for mes in meses:
            result = self._analyze_month({"month": mes, **parameters})
            if result["status"] == "analyzed":
                resultados.append(result["resumo"])
        
        # Calcular médias
        media_receitas = sum(r["total_entrou"] for r in resultados) / len(resultados) if resultados else 0
        media_lucro = sum(r["lucro_liquido"] for r in resultados) / len(resultados) if resultados else 0
        media_margem = sum(r["margem_lucro"] for r in resultados) / len(resultados) if resultados else 0
        
        # Saúde geral
        saude_geral = "Excelente ✅" if media_margem >= 30 else "Boa 👍" if media_margem >= 20 else "Atenção ⚠️" if media_margem >= 10 else "Crítica 🚨"
        
        return {
            "status": "checked",
            "saude_geral": saude_geral,
            "medias_ultimos_3_meses": {
                "receitas": round(media_receitas, 2),
                "lucro": round(media_lucro, 2),
                "margem": round(media_margem, 1)
            },
            "recomendacao": self._gerar_recomendacao_saude(saude_geral, media_margem)
        }
    
    # ==================== HELPERS ====================
    
    def _calcular_saude_financeira(
        self, 
        receitas: float, 
        despesas: float, 
        lucro: float, 
        margem: float
    ) -> str:
        """Calcula indicador de saúde financeira."""
        
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
        else:
            return "🔴 Crítica"
    
    def _check_limite_mei(self, receita_mensal: float, month: str) -> Dict[str, Any]:
        """Verifica se está dentro do limite MEI."""
        
        # Estimar faturamento anual
        mes_numero = int(month.split("-")[1])
        faturamento_anual_estimado = receita_mensal * 12
        
        # Calcular quanto pode faturar até o fim do ano
        meses_restantes = 12 - mes_numero
        limite_restante = self.LIMITE_ANUAL_MEI - (receita_mensal * mes_numero)
        
        percentual_usado = (receita_mensal * mes_numero) / self.LIMITE_ANUAL_MEI * 100
        
        if percentual_usado >= 100:
            status = "🚨 ULTRAPASSADO"
            alerta = "ATENÇÃO! Você já ultrapassou o limite MEI. Procure um contador para regularizar."
        elif percentual_usado >= 80:
            status = "⚠️ ATENÇÃO"
            alerta = f"Você já usou {percentual_usado:.1f}% do limite anual. Cuidado para não ultrapassar!"
        elif percentual_usado >= 60:
            status = "😊 NO LIMITE"
            alerta = f"Está usando {percentual_usado:.1f}% do limite. Continue monitorando."
        else:
            status = "✅ TRANQUILO"
            alerta = f"Você usou apenas {percentual_usado:.1f}% do limite anual. Tudo certo!"
        
        return {
            "status": status,
            "percentual_usado": round(percentual_usado, 1),
            "limite_anual": self.LIMITE_ANUAL_MEI,
            "faturamento_ate_agora": receita_mensal * mes_numero,
            "limite_restante": max(0, limite_restante),
            "alerta": alerta
        }
    
    def _gerar_insights_mensais(
        self, 
        receitas: float, 
        despesas: float, 
        lucro: float, 
        margem: float,
        saude: str
    ) -> List[str]:
        """Gera insights em linguagem simples."""
        
        insights = []
        
        # Análise de lucro
        if lucro > 0:
            insights.append(f"💚 Você lucrou R$ {lucro:.2f} este mês. Parabéns!")
        else:
            insights.append(f"🔴 Você teve prejuízo de R$ {abs(lucro):.2f}. Precisamos ajustar as contas.")
        
        # Análise de margem
        if margem >= 30:
            insights.append(f"🎯 Sua margem de lucro ({margem:.1f}%) está ótima! Para cada R$ 100 que entra, você fica com R$ {margem:.0f}.")
        elif margem >= 15:
            insights.append(f"👍 Margem de lucro razoável ({margem:.1f}%). Dá pra melhorar um pouco.")
        else:
            insights.append(f"⚠️ Margem muito baixa ({margem:.1f}%). Você está trabalhando quase de graça!")
        
        # Análise de despesas
        percentual_despesas = (despesas / receitas * 100) if receitas > 0 else 0
        if percentual_despesas > 70:
            insights.append(f"🚨 Suas despesas ({percentual_despesas:.0f}% da receita) estão comendo seu lucro! Hora de cortar gastos.")
        elif percentual_despesas > 50:
            insights.append(f"⚠️ Despesas altas ({percentual_despesas:.0f}% do que você ganha). Veja onde dá pra economizar.")
        
        # Comparação com limite ideal MEI
        if receitas < self.LIMITE_MENSAL_IDEAL * 0.5:
            insights.append(f"📊 Você pode faturar até R$ {self.LIMITE_MENSAL_IDEAL:.2f}/mês como MEI. Há espaço para crescer!")
        
        return insights
    
    def _gerar_recomendacoes(
        self, 
        receitas: float, 
        despesas: float, 
        lucro: float, 
        margem: float,
        limite_check: Dict[str, Any]
    ) -> List[str]:
        """Gera recomendações práticas."""
        
        recomendacoes = []
        
        # Recomendações por margem
        if margem < 15:
            recomendacoes.append("💡 Aumente seus preços! Você está cobrando muito barato.")
            recomendacoes.append("✂️ Corte despesas desnecessárias. Revise cada gasto.")
        
        # Recomendações por lucro
        if lucro < 0:
            recomendacoes.append("🚨 URGENTE: Reduza despesas ou aumente vendas. Você está perdendo dinheiro!")
        elif lucro < 1000:
            recomendacoes.append("📈 Busque mais clientes ou venda produtos/serviços de maior valor.")
        
        # Recomendações por limite
        if limite_check["percentual_usado"] >= 80:
            recomendacoes.append("⚠️ Procure um contador. Você pode precisar mudar para Simples Nacional.")
        
        # Recomendações gerais
        if len(recomendacoes) == 0:
            recomendacoes.append("✅ Continue assim! Seu negócio está saudável.")
            recomendacoes.append("💰 Pense em guardar parte do lucro para emergências.")
        
        return recomendacoes
    
    def _gerar_explicacao_simples(
        self,
        receitas: float,
        despesas: float,
        impostos: float,
        lucro: float,
        margem: float
    ) -> str:
        """Gera explicação em linguagem clara."""
        
        explicacao = f"""
📊 RESUMO DO SEU MÊS (em português claro!)

💵 O QUE ENTROU: R$ {receitas:.2f}
   └─ Tudo que você vendeu/recebeu

💸 O QUE SAIU: R$ {despesas:.2f}
   ├─ Suas despesas do negócio
   └─ Impostos (DAS): R$ {impostos:.2f}

{'💚' if lucro > 0 else '🔴'} O QUE SOBROU (Lucro): R$ {lucro:.2f}
   └─ É isso que você realmente ganhou

📈 MARGEM DE LUCRO: {margem:.1f}%
   └─ De cada R$ 100 que entra, você fica com R$ {margem:.0f}

Em outras palavras:
Você faturou R$ {receitas:.2f}, gastou R$ {despesas + impostos:.2f}, 
e {'lucrou' if lucro > 0 else 'teve prejuízo de'} R$ {abs(lucro):.2f}.
"""
        return explicacao.strip()
    
    def _gerar_explicacao_comparacao(
        self,
        mes_atual: Dict,
        mes_anterior: Dict,
        var_receitas: float,
        var_lucro: float,
        perc_receitas: float,
        perc_lucro: float
    ) -> str:
        """Gera explicação de comparação."""
        
        receitas_status = "subiu" if var_receitas > 0 else "caiu" if var_receitas < 0 else "ficou igual"
        lucro_status = "aumentou" if var_lucro > 0 else "diminuiu" if var_lucro < 0 else "ficou igual"
        
        explicacao = f"""
📊 COMPARAÇÃO ENTRE MESES

Suas vendas {receitas_status} {abs(perc_receitas):.1f}% 
({'+' if var_receitas > 0 else ''}{var_receitas:.2f})

Seu lucro {lucro_status} {abs(perc_lucro):.1f}%
({'+' if var_lucro > 0 else ''}{var_lucro:.2f})

{'🎉 Parabéns! Você está crescendo!' if var_lucro > 0 else '⚠️ Atenção! Vamos reverter essa queda.'}
"""
        return explicacao.strip()
    
    def _analisar_tendencia(self, resultados: List[Dict]) -> str:
        """Analisa tendência dos últimos meses."""
        
        if len(resultados) < 2:
            return "Sem dados suficientes para análise de tendência"
        
        # Verificar se lucro está crescendo
        lucros = [r["resumo"]["lucro_liquido"] for r in resultados]
        
        if all(lucros[i] < lucros[i+1] for i in range(len(lucros)-1)):
            return "📈 Crescimento consistente! Continue assim!"
        elif all(lucros[i] > lucros[i+1] for i in range(len(lucros)-1)):
            return "📉 Queda nos últimos meses. Hora de agir!"
        else:
            return "📊 Altos e baixos. Tente manter mais estabilidade."
    
    def _gerar_recomendacao_saude(self, saude: str, margem: float) -> str:
        """Gera recomendação baseada na saúde geral."""
        
        if "Crítica" in saude:
            return "🚨 Situação delicada! Procure ajuda de um contador ou consultor financeiro."
        elif "Atenção" in saude:
            return "⚠️ Revise seus gastos e veja onde pode melhorar."
        elif "Boa" in saude:
            return "👍 Está no caminho certo! Continue monitorando."
        else:
            return "✅ Parabéns! Seu negócio está saudável e lucrativo."
    
    def _load_financial_data(self, month: str) -> Optional[Dict[str, Any]]:
        """Tenta carregar dados financeiros de arquivo."""
        
        # Tentar carregar de data/mei_finances_example.json
        data_file = Path("data") / "mei_finances_example.json"
        
        if not data_file.exists():
            return None
        
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                all_data = json.load(f)
            
            # Se for um dict com o mês como chave
            if isinstance(all_data, dict) and month in all_data:
                return all_data[month]
            
            # Se for uma lista, procurar pelo mês
            if isinstance(all_data, list):
                for item in all_data:
                    if item.get("month") == month:
                        return item
            
            return None
        except Exception as e:
            logger.warning(f"Erro ao carregar dados financeiros: {e}")
            return None


def run_finance_agent(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Helper para executar o agente financeiro."""
    agent = FinanceAgent()
    return agent.execute(parameters)
