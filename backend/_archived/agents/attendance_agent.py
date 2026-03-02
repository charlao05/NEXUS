"""
Agente de Agendamento Passivo - Atendimentos com Clientes
Gerencia agendamentos que CLIENTES fazem com você (atendimentos, consultas, reuniões).
Cliente agenda → Você atende.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

try:
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..utils.logging_utils import get_logger

# Import the project's llm client; we'll adapt the call when we know its API
from backend.utils import llm_client

logger = get_logger(__name__)


@dataclass
class MensagemCliente:
    id: int
    canal: str
    nome_cliente: str
    texto: str


@dataclass
class SugestaoAgendamento:
    slots_sugeridos: List[str]
    observacoes: str


def carregar_agenda(path: str | Path) -> Dict[str, Any]:
    import json

    path = Path(path)
    if not path.exists():
        logger.error("Agenda não encontrada: %s", path)
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def carregar_mensagens(path: str | Path) -> List[MensagemCliente]:
    import json

    path = Path(path)
    if not path.exists():
        logger.error("Arquivo de mensagens não encontrado: %s", path)
        return []

    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    mensagens: List[MensagemCliente] = []
    for item in raw:
        mensagens.append(
            MensagemCliente(
                id=item.get("id"),
                canal=item.get("canal", "whatsapp"),
                nome_cliente=item.get("nome_cliente", "Cliente"),
                texto=item.get("texto", ""),
            )
        )
    return mensagens


def sugerir_slots_basicos(agenda: Dict[str, Any], quantidade: int = 3) -> List[str]:
    """
    Sugere alguns slots futuros, de forma simplificada.
    Usa as configurações de 'next_days_to_offer' e 'slot_duration_minutes'.
    """
    base = datetime.now().replace(minute=0, second=0, microsecond=0)
    slots: List[str] = []

    next_days = int(agenda.get("next_days_to_offer", 7))
    # duration configured but not used in this simplified suggester

    # Simples: varre os próximos 'next_days' e pega janelas nas horas 10, 14, 16
    candidate_hours = [10, 14, 16]
    for day_offset in range(1, next_days + 1):
        if len(slots) >= quantidade:
            break
        candidate_day = base + timedelta(days=day_offset)
        for hour in candidate_hours:
            if len(slots) >= quantidade:
                break
            slot_dt = candidate_day.replace(hour=hour, minute=0)
            slot_iso = slot_dt.strftime("%Y-%m-%d %H:%M")
            blocked = agenda.get("blocked_slots", [])
            if slot_dt.isoformat()[:16] in [b[:16] for b in blocked]:
                continue
            slots.append(slot_iso)

    # Fallback: se não conseguiu, retorna próximas 3 horas
    if not slots:
        for i in range(1, quantidade + 1):
            slots.append((base + timedelta(days=i)).strftime("%Y-%m-%d %H:%M"))

    return slots


def gerar_resposta_com_ia(
    mensagem: MensagemCliente, slots_sugeridos: List[str], contexto_negocio: str
) -> str:
    """
    Gera a resposta textual usando o LLM do projeto.
    Ajustaremos a chamada ao LLM caso o nome da função seja diferente em `llm_client`.
    """
    prompt = f"""
Você é um assistente de atendimento para um Microempreendedor Individual (MEI).

NEGÓCIO:
{contexto_negocio}

MENSAGEM DO CLIENTE:
Nome: {mensagem.nome_cliente}
Canal: {mensagem.canal}
Texto: {mensagem.texto}

SLOTS DISPONÍVEIS SUGERIDOS:
{slots_sugeridos}

TAREFA:
Responda em português brasileiro, com tom simpático e direto.
Se o cliente pediu horário, ofereça alguns dos slots sugeridos.
Se o cliente perguntou preço, responda com valor genérico.
Mantenha a resposta curta (máximo 100 palavras).
"""

    # Gera resposta de confirmação usando LLM
    try:
        resposta = llm_client.gerar_texto_simples(prompt)
    except (AttributeError, Exception):
        # Fallback: template simples sem LLM
        if "horário" in mensagem.texto.lower() or "hora" in mensagem.texto.lower():
            opções = " / ".join(slots_sugeridos)
            resposta = f"Olá {mensagem.nome_cliente}, temos os seguintes horários disponíveis: {opções}. Qual prefere?"
        else:
            resposta = f"Olá {mensagem.nome_cliente}, obrigado pela mensagem! Vou verificar e retorno em breve."

    return resposta.strip()


def processar_mensagens(
    agenda_path: str | Path, mensagens_path: str | Path, contexto_negocio: str
) -> List[Dict[str, Any]]:
    agenda = carregar_agenda(agenda_path)
    mensagens = carregar_mensagens(mensagens_path)

    resultados: List[Dict[str, Any]] = []

    for msg in mensagens:
        logger.info("Processando mensagem %s (%s)", msg.id, msg.canal)
        slots = sugerir_slots_basicos(agenda)
        resposta = gerar_resposta_com_ia(msg, slots, contexto_negocio)

        resultados.append(
            {
                "id": msg.id,
                "canal": msg.canal,
                "nome_cliente": msg.nome_cliente,
                "texto_original": msg.texto,
                "slots_sugeridos": slots,
                "resposta": resposta,
            }
        )

    return resultados


# Quick local test
if __name__ == "__main__":
    base = Path(__file__).resolve().parents[2]
    agenda_path = base / "data" / "mei_schedule.json"
    mensagens_path = base / "data" / "mensagens_clientes.json"
    ctx = "Salão de estética e beleza, Vila Velha/ES"
    out = processar_mensagens(agenda_path, mensagens_path, ctx)
    for r in out:
        print(r["id"], r["resposta"])
