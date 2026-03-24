"""
NEXUS - Telegram Webhook Router
Recebe e processa updates do Telegram.
"""

import hmac
import os
import logging

from fastapi import APIRouter, Request, HTTPException

from services.telegram_service import send_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])

WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Recebe updates do Telegram e processa comandos."""

    # Validar secret header (segurança)
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(token, WEBHOOK_SECRET):
            raise HTTPException(status_code=403, detail="Token inválido")

    update = await request.json()
    message = update.get("message") or update.get("edited_message")

    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return {"ok": True}

    text = (message.get("text") or "").strip()
    user = message.get("from", {})
    username = user.get("username", "usuário")

    logger.info(f"Telegram update de @{username} ({chat_id}): {text[:50]}")

    # Roteamento de comandos
    if text.startswith("/start"):
        await send_message(
            chat_id,
            f"👋 Olá, *{user.get('first_name', username)}*!\n\n"
            f"Bem-vindo ao *NEXUS Assistant*.\n\n"
            f"Para conectar sua conta NEXUS, acesse:\n"
            f"https://app.nexxusapp.com.br/settings/telegram\n\n"
            f"Digite /ajuda para ver todos os comandos.",
        )
    elif text.startswith("/ajuda"):
        await send_message(
            chat_id,
            "*Comandos disponíveis:*\n\n"
            "/clientes — Gerenciar clientes\n"
            "/agenda — Ver agendamentos\n"
            "/financeiro — Resumo financeiro\n"
            "/cobranca — Cobranças em aberto\n"
            "/nf — Emitir nota fiscal\n"
            "/status — Ver plano e uso\n",
        )
    else:
        await send_message(
            chat_id,
            "🤖 Processando sua mensagem...\n\n"
            "_Conecte sua conta em https://app.nexxusapp.com.br/settings/telegram "
            "para usar o assistente completo._",
        )

    return {"ok": True}
