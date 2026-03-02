"""Integração com Telegram Bot API."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import httpx

from backend.utils.logging_utils import get_logger

logger = get_logger(__name__)


class TelegramAPI:
    """Cliente para enviar mensagens via Telegram Bot API."""

    def __init__(self, bot_token: str | None = None):
        """
        Inicializar cliente Telegram.

        :param bot_token: Token do bot Telegram. Se não fornecido, usa TELEGRAM_BOT_TOKEN.
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

        if not self.bot_token:
            logger.error(
                "Telegram bot token not found. Set TELEGRAM_BOT_TOKEN in environment."
            )
            raise ValueError("Telegram bot token missing in environment or parameters.")

    def send_message(
        self,
        chat_id: str,
        message_text: str,
        parse_mode: str = "Markdown",
        disable_web_page_preview: bool = True,
    ) -> Dict[str, Any]:
        """
        Enviar uma mensagem de texto simples.

        :param chat_id: ID do chat/grupo/usuário (pode ser número ou @username).
        :param message_text: Conteúdo da mensagem (suporta Markdown ou HTML).
        :param parse_mode: "Markdown", "HTML" ou "MarkdownV2" (padrão: Markdown).
        :param disable_web_page_preview: Não mostrar preview de links (padrão: True).
        :return: Resposta da API (com message_id, status, etc.).
        """
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                if data.get("ok"):
                    msg_id = data.get("result", {}).get("message_id")
                    logger.info(
                        "Mensagem enviada para chat %s | message_id=%s", chat_id, msg_id
                    )
                    return data
                else:
                    error_msg = data.get("description", "Unknown error")
                    logger.error("Erro ao enviar mensagem Telegram: %s", error_msg)
                    return {"ok": False, "error": error_msg, "status": "failed"}
        except httpx.HTTPError as e:
            logger.exception("Erro de conexão ao enviar mensagem Telegram: %s", e)
            return {"ok": False, "error": str(e), "status": "failed"}

    def send_document(
        self,
        chat_id: str,
        document_url: str,
        caption: Optional[str] = None,
        parse_mode: str = "Markdown",
    ) -> Dict[str, Any]:
        """
        Enviar um documento/arquivo.

        :param chat_id: ID do chat/grupo/usuário.
        :param document_url: URL do documento (pública).
        :param caption: Legenda do documento (opcional).
        :param parse_mode: Formato de parsing (Markdown, HTML, etc.).
        :return: Resposta da API.
        """
        url = f"{self.base_url}/sendDocument"
        payload = {
            "chat_id": chat_id,
            "document": document_url,
        }
        if caption:
            payload["caption"] = caption
            payload["parse_mode"] = parse_mode

        try:
            with httpx.Client() as client:
                response = client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                if data.get("ok"):
                    msg_id = data.get("result", {}).get("message_id")
                    logger.info(
                        "Documento enviado para chat %s | message_id=%s",
                        chat_id,
                        msg_id,
                    )
                    return data
                else:
                    error_msg = data.get("description", "Unknown error")
                    logger.error("Erro ao enviar documento Telegram: %s", error_msg)
                    return {"ok": False, "error": error_msg, "status": "failed"}
        except httpx.HTTPError as e:
            logger.exception("Erro ao enviar documento Telegram: %s", e)
            return {"ok": False, "error": str(e), "status": "failed"}

    def send_photo(
        self,
        chat_id: str,
        photo_url: str,
        caption: Optional[str] = None,
        parse_mode: str = "Markdown",
    ) -> Dict[str, Any]:
        """
        Enviar uma foto/imagem.

        :param chat_id: ID do chat/grupo/usuário.
        :param photo_url: URL da foto (pública).
        :param caption: Legenda da foto (opcional).
        :param parse_mode: Formato de parsing.
        :return: Resposta da API.
        """
        url = f"{self.base_url}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
        }
        if caption:
            payload["caption"] = caption
            payload["parse_mode"] = parse_mode

        try:
            with httpx.Client() as client:
                response = client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                if data.get("ok"):
                    logger.info("Foto enviada para chat %s", chat_id)
                    return data
                else:
                    error_msg = data.get("description", "Unknown error")
                    logger.error("Erro ao enviar foto Telegram: %s", error_msg)
                    return {"ok": False, "error": error_msg, "status": "failed"}
        except httpx.HTTPError as e:
            logger.exception("Erro ao enviar foto Telegram: %s", e)
            return {"ok": False, "error": str(e), "status": "failed"}


def send_nf_notification(
    chat_id: str,
    client_name: str,
    nf_value: float,
    custom_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enviar notificação de nota fiscal via Telegram (exemplo prático).

    :param chat_id: ID do chat/usuário do cliente.
    :param client_name: Nome do cliente.
    :param nf_value: Valor da nota fiscal.
    :param custom_message: Mensagem customizada (se None, usa padrão).
    :return: Resposta da API.
    """
    api = TelegramAPI()

    if custom_message is None:
        custom_message = (
            f"👋 Olá {client_name}!\n\n"
            f"✅ Sua nota fiscal foi gerada com sucesso!\n\n"
            f"💰 *Valor:* R$ {nf_value:.2f}\n\n"
            f"Se tiver dúvidas, é só chamar! 📞"
        )

    return api.send_message(chat_id, custom_message)


if __name__ == "__main__":
    # Teste local (requer TELEGRAM_BOT_TOKEN e TELEGRAM_TEST_CHAT_ID em .env)
    test_chat_id = os.getenv("TELEGRAM_TEST_CHAT_ID", "123456789")
    try:
        api = TelegramAPI()
        result = api.send_message(
            test_chat_id,
            "✅ Teste de integração Telegram do NEXUS!\n\n"
            "Você pode:\n"
            "• Enviar instruções de notas fiscais\n"
            "• Mensagens de cobrança automática\n"
            "• Notificações de atendimento\n"
            "• E muito mais!",
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except ValueError as e:
        print(f"Erro: {e}")
