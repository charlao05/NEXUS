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
# Catálogo de serviços — DE CADA CLIENTE DO NEXUS, não da plataforma.
#
# Antes havia aqui uma lista fixa (Landing Page, MVP de SaaS…) que era o
# catálogo do PRÓPRIO Alinha. Isso quebrava o agente para o público-alvo: uma
# cabeleireira MEI abria o VENDAS e via "MVP de Software SaaS — R$ 25.000".
# Agora os serviços vêm da tabela `products` com item_type='servico', SEMPRE
# filtrados pelo user_id de quem chamou (InventoryService já é multi-tenant).
#
# ATENÇÃO multi-tenant: VendasAgent é instanciado como SINGLETON compartilhado
# no agent_hub. NUNCA guardar user_id/serviços no self — o user_id vem em
# `parameters` a cada chamada (a rota injeta) e é usado apenas localmente.
# ---------------------------------------------------------------------------
MOEDA = "BRL"

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


def _servicos_do_usuario(user_id: Any) -> List[Dict[str, Any]]:
    """Catálogo de serviços DESTE usuário (item_type='servico').

    Sempre filtrado por user_id pelo InventoryService — nunca retorna serviço
    de outro tenant. Sem user_id válido, devolve lista vazia (fail-closed).
    """
    try:
        uid = int(user_id or 0)
    except (TypeError, ValueError):
        return []
    if uid <= 0:
        return []
    try:
        from database.inventory_service import InventoryService
        res = InventoryService.get_products(
            user_id=uid, item_type="servico", is_active=True, limit=200,
        )
        return list((res or {}).get("products", []))
    except Exception as e:  # noqa: BLE001
        logger.error("Falha ao ler serviços do usuário %s: %s", uid, e,
                     exc_info=True)
        return []


_SEM_SERVICOS = (
    "📋 **Você ainda não cadastrou seus serviços.**\n\n"
    "O NEXUS precifica *o seu* serviço — não um catálogo genérico. "
    "Use a ação **Cadastrar Serviço** para registrar o que você faz e o "
    "preço-base (ex.: \"Corte de cabelo\" · R$ 45).\n"
    "Depois disso, o orçamento e a proposta saem prontos."
)


class VendasAgent:
    """Agente de vendas: catálogo, precificação, qualificação e proposta."""

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        action = parameters.get("action", "listar_servicos")
        dispatch = {
            "listar_servicos": self._listar_servicos,
            "cadastrar_servico": self._cadastrar_servico,
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
    def _listar_servicos(self, p: Dict[str, Any]) -> Dict[str, Any]:
        servicos = _servicos_do_usuario(p.get("user_id"))
        if not servicos:
            return {"status": "ok", "message": _SEM_SERVICOS,
                    "servicos": [], "moeda": MOEDA}

        linhas = [f"• {s['name']}: {_brl(s.get('sale_price') or 0)}"
                  for s in servicos]
        return {
            "status": "ok",
            "message": ("💼 **Seus serviços**\n" + "\n".join(linhas)
                        + "\n\n_Use \"Calcular Orçamento\" para aplicar "
                          "urgência e complexidade sobre esses preços._"),
            "moeda": MOEDA,
            "servicos": [
                {"id": s["id"], "nome": s["name"],
                 "preco_base": s.get("sale_price") or 0,
                 "preco_base_formatado": _brl(s.get("sale_price") or 0)}
                for s in servicos
            ],
            "modificadores": MODIFICADORES,
        }

    def _cadastrar_servico(self, p: Dict[str, Any]) -> Dict[str, Any]:
        """Registra um serviço no catálogo DO USUÁRIO."""
        try:
            uid = int(p.get("user_id") or 0)
        except (TypeError, ValueError):
            uid = 0
        if uid <= 0:
            return {"status": "error",
                    "message": "⚠️ Não identifiquei sua conta. Recarregue a página e tente de novo."}

        nome = str(p.get("nome") or p.get("name") or "").strip()
        if not nome:
            return {"status": "error",
                    "message": "⚠️ Informe o nome do serviço (ex.: \"Corte de cabelo\")."}
        try:
            preco = float(p.get("preco_base") or p.get("sale_price") or 0)
        except (TypeError, ValueError):
            preco = 0.0
        if preco <= 0:
            return {"status": "error",
                    "message": "⚠️ Informe um preço-base maior que zero para o serviço."}

        from database.inventory_service import InventoryService
        res = InventoryService.create_product(
            user_id=uid,
            name=nome,
            sale_price=preco,
            unit="serviço",
            category=str(p.get("categoria") or "").strip() or None,
            item_type="servico",
        )
        if res.get("status") != "created":
            return {"status": "error",
                    "message": f"⚠️ Não consegui cadastrar: {res.get('message', 'erro desconhecido')}"}

        return {
            "status": "ok",
            "message": (f"✅ Serviço cadastrado: **{nome}** — {_brl(preco)}\n\n"
                        "Agora ele aparece em \"Calcular Orçamento\" e "
                        "\"Gerar Proposta\"."),
            "servico": res.get("product"),
        }

    def _preco(self, requisitos: Dict[str, Any]) -> Dict[str, Any]:
        """Núcleo de precificação (multiplicadores do pricing_engine do Alinha,
        aplicados sobre o preço-base do serviço DO USUÁRIO)."""
        service_id = requisitos.get("service_type") or requisitos.get("servico")
        urgency = (requisitos.get("urgency") or requisitos.get("urgencia")
                   or "medium")
        tech = (requisitos.get("technical_details")
                or requisitos.get("detalhes_tecnicos") or "").lower()

        # Busca no catálogo DO USUÁRIO: por id numérico ou por nome.
        servicos = _servicos_do_usuario(requisitos.get("user_id"))
        servico = None
        if service_id is not None and str(service_id).strip():
            alvo = str(service_id).strip().lower()
            servico = next(
                (s for s in servicos if str(s["id"]) == alvo), None
            ) or next(
                (s for s in servicos if str(s["name"]).strip().lower() == alvo), None
            )

        if servico is None:
            # Sem serviço identificado: usa preço avulso informado, se houver.
            try:
                base = float(requisitos.get("preco_base") or 0)
            except (TypeError, ValueError):
                base = 0.0
            nome = str(requisitos.get("nome_servico") or "").strip() or "Serviço avulso"
            if base <= 0:
                base = _PRECO_CUSTOM_PADRAO
        else:
            base = float(servico.get("sale_price") or 0)
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
        # Sem catálogo e sem preço avulso, orientar em vez de inventar valor.
        if not _servicos_do_usuario(p.get("user_id")):
            try:
                _avulso = float(p.get("preco_base") or 0)
            except (TypeError, ValueError):
                _avulso = 0.0
            if _avulso <= 0:
                return {"status": "ok", "message": _SEM_SERVICOS, "servicos": []}

        preco = self._preco(p)
        mult = ", ".join(preco["multiplicadores_aplicados"])
        msg = (
            f"💼 **Orçamento — {preco['servico']}**\n"
            f"Valor: **{preco['valor_total_formatado']}** "
            f"(base {_brl(preco['valor_base'])}; multiplicadores: {mult})\n"
            f"Manutenção mensal: {preco['manutencao_mensal_formatada']}"
        )
        return {"status": "ok", "message": msg, **preco}

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
        recomendacao = {
            "quente": "Priorizar: enviar proposta hoje.",
            "morno": "Nutrir: enviar demo + case, follow-up em 3 dias.",
            "frio": "Baixa prioridade: material educativo, sem esforço de venda.",
        }[faixa]
        return {
            "status": "ok",
            "message": f"🎯 Lead **{faixa}** — score {score}/100. {recomendacao}",
            "score": score,
            "faixa": faixa,
            "recomendacao": recomendacao,
        }

    def _gerar_proposta(self, p: Dict[str, Any]) -> Dict[str, Any]:
        """Gera proposta comercial. Usa OpenAI se disponível; senão template."""
        preco = self._preco(p)
        cliente = p.get("cliente") or p.get("client") or "Cliente"
        escopo = p.get("escopo") or p.get("descricao") or preco["servico"]

        proposta_template = self._proposta_template(cliente, escopo, preco)

        # Enriquecer com IA usando o helper padrão do hub (mesma interface que os
        # demais agentes). Antes chamava client.chat.completions.create() no
        # wrapper OpenAIClient, que só expõe chat_completion() → sempre falhava e
        # caía no template. Graceful: sem chave/erro, mantém o template.
        texto_ia = None
        try:
            from utils.llm_client import gerar_texto_simples  # type: ignore
            prompt = (
                "Você é um redator comercial. Gere uma proposta de serviço "
                f"(SOW) profissional e objetiva em português para o cliente "
                f"'{cliente}'. Serviço: {preco['servico']}. Escopo: {escopo}. "
                f"Investimento: {preco['valor_total_formatado']} "
                f"(+ manutenção {preco['manutencao_mensal_formatada']}/mês). "
                "Estruture em: Contexto, Escopo, Entregáveis, Investimento, "
                "Prazo, Próximos passos."
            )
            texto = gerar_texto_simples(prompt, max_tokens=800, temperature=0.4)
            if texto and texto.strip():
                texto_ia = texto.strip()
        except Exception as e:  # noqa: BLE001
            logger.info("Proposta sem IA (fallback template): %s", e)

        return {
            "status": "ok",
            "message": texto_ia or proposta_template,
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
