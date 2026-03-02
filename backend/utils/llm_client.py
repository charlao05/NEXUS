# src/utils/llm_client.py

"""
Cliente de LLM para gerar plano de ação em JSON.

- Usa a API da OpenAI (chat completions).
- Gera um plano de ações para automatizar um site via navegador.
"""

import json
import os
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

from .logging_utils import get_logger

load_dotenv()

logger = get_logger(__name__)

# flake8: noqa: E501

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY não encontrado no ambiente (.env).")

client = OpenAI(api_key=api_key)


def _extrair_json(texto: str) -> str:
    """
    Tenta extrair um JSON de dentro de um texto qualquer.
    Pega da primeira '{' até a última '}'.
    """
    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio == -1 or fim == -1 or fim <= inicio:
        raise ValueError("Não foi possível encontrar JSON na resposta do modelo.")
    return texto[inicio : fim + 1]


def gerar_plano_acao(
    site: str, objetivo: str, contexto_site: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Gera um PLANO DE AÇÃO em JSON para automatizar um site via navegador.

    Retorno esperado:
    {
      "steps": [
        {
          "tipo": "open_url" | "click" | "type" | "wait_selector",
          "parametros": {
            "url": "...",
            "selector": "...",
            "text": "...",
            "timeout_ms": 10000
          }
        }
      ]
    }
    """

    contexto_serializado = json.dumps(contexto_site, ensure_ascii=False, indent=2)

    system_msg = (
        "Você é um agente de automação para Agência de IA focado em marketing, vendas e atendimento. "
        "Sua tarefa é gerar planos de automação web usando Playwright com base em objetivos descritos em linguagem natural.\n\n"
        "TIPOS DE AÇÃO SUPORTADOS:\n"
        "- 'open_url': Abre uma URL.\n"
        "- 'wait_selector': Aguarda um elemento aparecer na página.\n"
        "- 'click': Clica em um elemento.\n"
        "- 'type': Digita texto em um campo.\n"
        "- 'press_key': Pressiona uma tecla (ex: 'Enter', 'Tab').\n"
        "- 'wait_seconds': Aguarda N segundos.\n\n"
        "REGRAS OBRIGATÓRIAS:\n"
        "1. Responda SEMPRE com um JSON válido, sem nenhum texto fora do JSON.\n"
        "2. Use EXATAMENTE este formato:\n"
        '{"steps": [{"tipo": "open_url" | "click" | "type" | "wait_selector" | "press_key" | "wait_seconds", '
        '"parametros": {"url": "", "selector": "", "text": "", "key": "", "seconds": 0, "timeout_ms": 10000}}]}\n'
        "3. Apenas inclua os parametros relevantes para cada tipo de ação.\n"
        "4. Não invente username ou senha; use placeholders se necessário.\n"
        "5. Use seletores CSS válidos (classes, IDs, atributos).\n"
    )

    user_msg = f"""
Site alvo: {site}

Objetivo do usuário:
{objetivo}

Contexto do site (configuração em JSON):
{contexto_serializado}

REGRAS OBRIGATÓRIAS:

- Responda SOMENTE com um JSON válido.
- Use o seguinte formato:

{{
  "steps": [
    {{
      "tipo": "open_url" | "click" | "type" | "wait_selector" | "press_key" | "wait_seconds",
      "parametros": {{
        "url": "URL para open_url",
        "selector": "seletor CSS",
        "text": "texto para type",
        "key": "tecla para press_key",
        "seconds": "segundos para wait_seconds",
        "timeout_ms": 10000
      }}
    }}
  ]
}}

- Não escreva nenhum texto fora do JSON.
- Não invente usuário ou senha.
- Use apenas tipos de ação suportados.
"""

    logger.info("Chamando modelo OpenAI para gerar plano de ação.")

    resposta = client.chat.completions.create(
        model="gpt-4o-mini",  # pode trocar para outro modelo compatível se quiser
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
    )

    conteudo = resposta.choices[0].message.content or ""
    logger.debug("Resposta bruta do modelo:\n%s", conteudo)

    # Extrai só o JSON do texto
    json_bruto = _extrair_json(conteudo)

    # Faz o parse do JSON
    try:
        plano = json.loads(json_bruto)
    except json.JSONDecodeError as exc:
        logger.error("Falha ao fazer parse do JSON: %s", exc)
        raise ValueError("JSON retornado pelo modelo é inválido.") from exc

    if not isinstance(plano, dict) or "steps" not in plano:
        logger.error("JSON não contém campo 'steps': %s", plano)
        raise ValueError("JSON retornado não tem o campo 'steps'.")

    logger.info("Plano de ação gerado com sucesso: %d passos.", len(plano["steps"]))
    return plano


def gerar_texto_simples(
    prompt: str, max_tokens: int = 200, temperature: float = 0.2
) -> str:
    """
    Gera um texto simples a partir de um prompt em linguagem natural.

    Uso: respostas curtas para atendimento, mensagens, resumos.
    Retorna o texto bruto retornado pelo modelo.
    """
    logger.info("Chamando modelo OpenAI para gerar texto simples.")
    resposta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Você é um assistente útil que responde em português de forma curta e direta.",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )

    conteudo = resposta.choices[0].message.content or ""
    logger.debug("Resposta bruta do modelo (texto simples): %s", conteudo)
    return conteudo.strip()
