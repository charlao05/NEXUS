"""
Agente de Vendas — NEXUS
=========================

Motor de vendas B2B migrado do projeto Alinha (simbiose NEXUS × Alinha).
Qualifica o lead, precifica o serviço e gera a proposta comercial (SOW).

Portado de: Alinha/src/core/pricing_engine.py, intake_agent.py, scoping_agent.py.

Ações (parameters["action"]):
  - listar_servicos      : catálogo de serviços e preços-base
  - calcular_orcamento   : preço com multiplicadores de urgência/complexidade
  - qualificar_lead      : score simples do lead a partir das respostas
  - gerar_proposta       : proposta comercial (usa OpenAI se disponível;
                           senão, template determinístico)

Design: STATELESS (não acessa o banco). Precificação é pura → sem risco
multi-tenant. Se futuramente persistir propostas, threadar `user_id` como
os demais agentes (padrão do commit 06d7089).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Catálogo de serviços (embutido — auto-contido, sem depender de JSON externo)
# Migrado de Alinha/data/alinha/price_table.json
# ---------------------------------------------------------------------------
MOEDA = "BRL"

SERVICOS: List[Dict[str, Any]] = [
    {"id": "landing_page", "name": "Landing Page de Conversão",
     "base_price": 2500.0, "hourly_rate": 150.0, "estimated_hours": 20},
    {"id": "ecommerce_basic", "name": "E-commerce Básico (Shopify/WooCommerce)",
     "base_price": 8000.0, "hourly_rate": 180.0, "estimated_hours": 60},
    {"id": "api_integration", "name": "Integração de API Customizada",
     "base_price": 3500.0, "hourly_rate": 200.0, "estimated_hours": 24},
    {"id": "saas_mvp", "name": "MVP de Software SaaS",
     "base_price": 25000.0, "hourly_rate": 250.0, "estimated_hours": 160},
    {"id": "automation_audit", "name": "Auditoria de Processos e Automação",
     "base_price": 1500.0, "hourly_rate": 150.0, "estimated_hours": 10},
    {"id": "ai_agent_custom", "name": "Agente de IA Customizado",
     "base_price": 12000.0, "hourly_rate": 220.0, "estimated_hours": 50},
]

MODIFICADORES = {
    "urgency_multiplier": 1.5,
    "complexity_high": 1.3,
    "complexity_low": 0.9,
    "maintenance_monthly_rate": 0.1,   # manutenção mensal = 10% do projeto
}

_PRECO_CUSTOM_PADRAO = 5000.0
_GATILHOS_COMPLEXIDADE = [
    "sap", "integração", "integracao", "api", "segurança", "seguranca",
    "biometria", "migração", "migracao", "compliance", "erp",
]


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class VendasAgent:
    """Agente de vendas: catálogo, precificação, qualificação e proposta."""

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        action = parameters.get("action", "listar_servicos")
        dispatch = {
            "listar_servicos": self._listar_servicos,
            "calcular_orcamento": self._calcular_orcamento,
            "qualificar_lead": self._qualificar_lead,
            "gerar_proposta": self._gerar_proposta,
        }
        handler = dispatch.get(action)
        if handler is None:
            return {
                "status": "error",
                "message": (f"Ação desconhecida: {action}. "
                            f"Disponíveis: {list(dispatch.keys())}"),
            }
        try:
            return handler(parameters)
        except Exception as e:  # noqa: BLE001
            logger.error("Erro no agente vendas (action=%s): %s", action, e,
                         exc_info=True)
            return {"status": "error",
                    "message": f"Erro ao executar '{action}': {e}"}

    # ------------------------------------------------------------------ ações
    def _listar_servicos(self, _p: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "ok",
            "moeda": MOEDA,
            "servicos": [
                {"id": s["id"], "nome": s["name"],
                 "preco_base": s["base_price"],
                 "preco_base_formatado": _brl(s["base_price"]),
                 "horas_estimadas": s["estimated_hours"]}
                for s in SERVICOS
            ],
            "modificadores": MODIFICADORES,
        }

    def _preco(self, requisitos: Dict[str, Any]) -> Dict[str, Any]:
        """Núcleo de precificação (porte fiel do pricing_engine do Alinha)."""
        service_id = requisitos.get("service_type") or requisitos.get("servico")
        urgency = (requisitos.get("urgency") or requisitos.get("urgencia")
                   or "medium")
        tech = (requisitos.get("technical_details")
                or requisitos.get("detalhes_tecnicos") or "").lower()

        servico = next((s for s in SERVICOS if s["id"] == service_id), None)
        if servico is None:
            base = _PRECO_CUSTOM_PADRAO
            nome = "Projeto Customizado"
        else:
            base = servico["base_price"]
            nome = servico["name"]

        total = base
        aplicou = []

        # 1. urgência
        if str(urgency).lower() in ("high", "alta"):
            total *= MODIFICADORES["urgency_multiplier"]
            aplicou.append("urgência (×1,5)")

        # 2. complexidade
        is_complexo = (any(g in tech for g in _GATILHOS_COMPLEXIDADE)
                       or len(tech) > 100)
        if is_complexo:
            total *= MODIFICADORES["complexity_high"]
            aplicou.append("complexidade alta (×1,3)")

        manutencao = round(total * MODIFICADORES["maintenance_monthly_rate"], 2)
        return {
            "servico": nome,
            "servico_id": service_id,
            "valor_base": base,
            "valor_total": round(total, 2),
            "valor_total_formatado": _brl(round(total, 2)),
            "manutencao_mensal": manutencao,
            "manutencao_mensal_formatada": _brl(manutencao),
            "moeda": MOEDA,
            "multiplicadores_aplicados": aplicou or ["nenhum"],
        }

    def _calcular_orcamento(self, p: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", **self._preco(p)}

    def _qualificar_lead(self, p: Dict[str, Any]) -> Dict[str, Any]:
        """Score simples de qualificação (0-100) a partir das respostas."""
        orcamento = float(p.get("orcamento_declarado", 0) or 0)
        prazo_dias = int(p.get("prazo_dias", 0) or 0)
        tem_decisor = bool(p.get("tem_decisor", False))
        dor_clara = bool(p.get("dor_clara", False))

        score = 0
        if orcamento >= 5000:
            score += 35
        elif orcamento >= 1500:
            score += 20
        elif orcamento > 0:
            score += 10
        if tem_decisor:
            score += 25
        if dor_clara:
            score += 25
        if 0 < prazo_dias <= 90:
            score += 15

        faixa = ("quente" if score >= 70 else
                 "morno" if score >= 40 else "frio")
        return {
            "status": "ok",
            "score": score,
            "faixa": faixa,
            "recomendacao": {
                "quente": "Priorizar: enviar proposta hoje.",
                "morno": "Nutrir: enviar demo + case, follow-up em 3 dias.",
                "frio": "Baixa prioridade: material educativo, sem esforço de venda.",
            }[faixa],
        }

    def _gerar_proposta(self, p: Dict[str, Any]) -> Dict[str, Any]:
        """Gera proposta comercial. Usa OpenAI se disponível; senão template."""
        preco = self._preco(p)
        cliente = p.get("cliente") or p.get("client") or "Cliente"
        escopo = p.get("escopo") or p.get("descricao") or preco["servico"]

        proposta_template = self._proposta_template(cliente, escopo, preco)

        # Tentativa opcional de enriquecer com IA (graceful se sem chave)
        texto_ia = None
        try:
            from helpers.openai_client import get_openai_client  # type: ignore
            client = get_openai_client()
            if client is not None:
                prompt = (
                    "Você é um redator comercial. Gere uma proposta de serviço "
                    f"(SOW) profissional e objetiva em português para o cliente "
                    f"'{cliente}'. Serviço: {preco['servico']}. Escopo: {escopo}. "
                    f"Investimento: {preco['valor_total_formatado']} "
                    f"(+ manutenção {preco['manutencao_mensal_formatada']}/mês). "
                    "Estruture em: Contexto, Escopo, Entregáveis, Investimento, "
                    "Prazo, Próximos passos."
                )
                resp = client.chat.completions.create(
                    model=p.get("model", "gpt-4o-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    timeout=30,
                )
                texto_ia = resp.choices[0].message.content
        except Exception as e:  # noqa: BLE001
            logger.info("Proposta sem IA (fallback template): %s", e)

        return {
            "status": "ok",
            "cliente": cliente,
            "precificacao": preco,
            "proposta": texto_ia or proposta_template,
            "gerada_por": "ia" if texto_ia else "template",
        }

    @staticmethod
    def _proposta_template(cliente: str, escopo: str,
                           preco: Dict[str, Any]) -> str:
        return (
            f"PROPOSTA COMERCIAL — {cliente}\n"
            f"{'=' * 40}\n\n"
            f"Serviço: {preco['servico']}\n"
            f"Escopo: {escopo}\n\n"
            f"Investimento: {preco['valor_total_formatado']}\n"
            f"Manutenção mensal: {preco['manutencao_mensal_formatada']}\n"
            f"Multiplicadores: {', '.join(preco['multiplicadores_aplicados'])}\n\n"
            "Próximos passos: aprovar esta proposta para iniciarmos o "
            "alinhamento técnico e o cronograma.\n"
        )


def run_vendas_agent(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point do agente (padrão dos demais agentes do hub)."""
    return VendasAgent().execute(parameters)
