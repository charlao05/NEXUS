"""
Módulo de Qualificação de Leads
================================

Workflow: Classificar leads coletados (formulário, CRM, etc.) usando IA.

Caso de uso:
- Recebe respostas de formulário (Google Forms, Typeform, etc.)
- Classifica em: Quente, Morno, Frio
- Gera justificativa e ação sugerida
- Usa LLM sem navegador (processamento puro de texto)

Produto que você vende:
- Setup: Integração com CRM/formulário da cliente
- Recorrência: Ajuste de critérios, análise mensal, otimização
"""

from __future__ import annotations

import json
from typing import Any, Dict

from openai import OpenAI
from dotenv import load_dotenv
import os

try:
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..utils.logging_utils import get_logger

load_dotenv()

logger = get_logger(__name__)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY não encontrado no ambiente (.env).")

client = OpenAI(api_key=api_key)


def _extrair_json_qualificacao(texto: str) -> str:
    """Extrai JSON de resposta do modelo para qualificação."""
    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio == -1 or fim == -1 or fim <= inicio:
        raise ValueError("Não foi possível encontrar JSON na resposta do modelo.")
    return texto[inicio : fim + 1]


def qualificar_lead(
    respostas_form: Dict[str, Any], contexto_nicho: str = ""
) -> Dict[str, Any]:
    """
    Classifica um lead em Quente, Morno ou Frio com base em respostas de formulário.

    Args:
        respostas_form: Dicionário com dados do lead (ex: {"nome": "João", "interesse": "Alto", ...})
        contexto_nicho: Contexto adicional (ex: "Imobiliária de luxo em SP")

    Retorna:
        {
            "classificacao": "Quente" | "Morno" | "Frio",
            "pontuacao": 8.5,  # 0-10
            "justificativa": "Lorem ipsum...",
            "acao_sugerida": "Ligar em até 1h",
            "tags": ["urgente", "alto_valor"]
        }
    """

    logger.info("Qualificando lead: %s", respostas_form)

    # Montar texto com dados do lead
    dados_texto = "\n".join(
        f"• {chave}: {valor}" for chave, valor in respostas_form.items()
    )

    system_msg = (
        "Você é um especialista em qualificação de leads para agências de marketing e vendas. "
        "Analise o lead fornecido e classifique-o em QUENTE, MORNO ou FRIO. "
        "Considere: urgência, orçamento, alinhamento com produto, prazo de compra. "
        "Responda SEMPRE com um JSON válido, sem texto fora do JSON."
    )

    user_msg = f"""
Contexto: {contexto_nicho if contexto_nicho else "Não especificado"}

Dados do Lead:
{dados_texto}

Analise e retorne um JSON com a seguinte estrutura:
{{
  "classificacao": "Quente" ou "Morno" ou "Frio",
  "pontuacao": número de 0 a 10,
  "justificativa": "Por que essa classificação?",
  "acao_sugerida": "Ação recomendada (ex: Ligar, Enviar proposta, Aguardar)",
  "tags": ["tag1", "tag2"]
}}

Regras:
- QUENTE: Alto interesse, orçamento definido, prazo curto (até 30 dias)
- MORNO: Interesse médio, precisa mais informações, prazo indefinido
- FRIO: Baixo interesse, sem urgência, pesquisa inicial

Responda APENAS com o JSON, sem texto adicional.
"""

    logger.info("Chamando OpenAI para qualificar lead...")

    try:
        resposta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
        )

        conteudo = resposta.choices[0].message.content or ""
        logger.debug("Resposta bruta do modelo:\n%s", conteudo)

        # Extrai JSON
        json_bruto = _extrair_json_qualificacao(conteudo)
        qualificacao = json.loads(json_bruto)

        logger.info(
            "Lead qualificado como: %s (pontuação: %s)",
            qualificacao.get("classificacao"),
            qualificacao.get("pontuacao"),
        )

        return qualificacao

    except json.JSONDecodeError as exc:
        logger.error("Falha ao fazer parse do JSON: %s", exc)
        raise ValueError("JSON retornado pelo modelo é inválido.") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erro ao qualificar lead: %s", exc)
        raise


def qualificar_lote_leads(
    lista_leads: list[Dict[str, Any]], contexto_nicho: str = ""
) -> list[Dict[str, Any]]:
    """
    Qualifica múltiplos leads em lote.

    Args:
        lista_leads: Lista de dicionários, cada um com dados do lead.
        contexto_nicho: Contexto compartilhado para todos os leads.

    Retorna:
        Lista de qualificações (cada uma com classificacao, pontuacao, etc.)
    """

    logger.info("Qualificando lote de %d leads...", len(lista_leads))

    resultados = []
    for idx, lead in enumerate(lista_leads, start=1):
        try:
            logger.info("Lead %d/%d", idx, len(lista_leads))
            qualif = qualificar_lead(lead, contexto_nicho)
            resultados.append(
                {
                    "lead": lead,
                    "qualificacao": qualif,
                    "status": "sucesso",
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Erro ao qualificar lead %d: %s", idx, exc)
            resultados.append(
                {
                    "lead": lead,
                    "qualificacao": None,
                    "status": "erro",
                    "erro": str(exc),
                }
            )

    logger.info(
        "Lote processado: %d sucessos, %d erros",
        sum(1 for r in resultados if r["status"] == "sucesso"),
        sum(1 for r in resultados if r["status"] == "erro"),
    )

    return resultados


if __name__ == "__main__":  # pragma: no cover
    # Exemplo de uso
    exemplo_lead = {
        "nome": "João Silva",
        "email": "joao@email.com",
        "telefone": "11999999999",
        "interesse": "Compra de imóvel",
        "orçamento": "R$ 500.000",
        "prazo": "Precisa em 15 dias",
        "origem": "Landing page",
    }

    print("Qualificando exemplo de lead...\n")
    resultado = qualificar_lead(
        exemplo_lead, contexto_nicho="Imobiliária de luxo em São Paulo"
    )
    print(f"\nResultado:\n{json.dumps(resultado, indent=2, ensure_ascii=False)}")
