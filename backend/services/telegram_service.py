"""
NEXUS - Telegram Service
Envia mensagens, notificações e alertas via Telegram Bot API.
"""

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def send_message(
    chat_id: str | int,
    text: str,
    parse_mode: str = "Markdown",
    reply_markup: Optional[dict] = None,
) -> bool:
    """Envia mensagem de texto para um chat do Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN não configurado")
        return False
    try:
        payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{TELEGRAM_API_BASE}/sendMessage", json=payload)
            if not resp.is_success:
                logger.error(f"Telegram send_message falhou: {resp.text}")
                return False
            return True
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem Telegram: {e}")
        return False


async def send_invoice_reminder(
    chat_id: str | int, client_name: str, amount: float, due_date: str
) -> bool:
    """Envia lembrete de cobrança via Telegram."""
    text = (
        f"💰 *Lembrete de Cobrança — NEXUS*\n\n"
        f"Cliente: *{client_name}*\n"
        f"Valor: *R$ {amount:.2f}*\n"
        f"Vencimento: *{due_date}*\n\n"
        f"Acesse o NEXUS para mais detalhes: https://app.nexxusapp.com.br"
    )
    return await send_message(chat_id, text)


async def send_das_reminder(
    chat_id: str | int, reference: str, due_date: str
) -> bool:
    """Envia lembrete de DAS via Telegram."""
    text = (
        f"📋 *Lembrete DAS — NEXUS*\n\n"
        f"Competência: *{reference}*\n"
        f"Vencimento: *{due_date}*\n\n"
        f"Não esqueça de pagar o DAS para manter seu MEI em dia!\n"
        f"Acesse: https://app.nexxusapp.com.br"
    )
    return await send_message(chat_id, text)


async def send_appointment_reminder(
    chat_id: str | int, title: str, client_name: str, scheduled_at: str
) -> bool:
    """Envia lembrete de agendamento via Telegram."""
    text = (
        f"📅 *Lembrete de Agendamento — NEXUS*\n\n"
        f"*{title}*\n"
        f"Cliente: {client_name}\n"
        f"Horário: *{scheduled_at}*\n\n"
        f"Acesse: https://app.nexxusapp.com.br"
    )
    return await send_message(chat_id, text)


async def notify_admin(message: str) -> bool:
    """Envia notificação para o admin do sistema."""
    admin_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
    if not admin_chat_id:
        logger.debug("TELEGRAM_ADMIN_CHAT_ID não configurado — notificação ignorada")
        return False
    return await send_message(admin_chat_id, f"🔔 *Admin NEXUS*\n\n{message}")
