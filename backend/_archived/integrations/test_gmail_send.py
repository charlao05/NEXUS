#!/usr/bin/env python
"""Script interativo para testar envio real via Gmail API.

Antes de rodar, configure no .env:
- GMAIL_SERVICE_ACCOUNT_FILE ou GMAIL_CREDENTIALS_FILE
- GMAIL_DELEGATED_USER (se usar Service Account)
- SENDER_EMAIL

Execução:
python -m src.integrations.test_gmail_send
"""

import os
from dotenv import load_dotenv
from backend.integrations.gmail_api import GmailAPI
from backend.utils.logging_utils import get_logger

logger = get_logger("test_gmail_send")

if __name__ == "__main__":
    load_dotenv()

    print("\n" + "=" * 60)
    print("TESTE DE ENVIO VIA GMAIL API")
    print("=" * 60 + "\n")

    # Verificar configuração
    svc_file = os.getenv("GMAIL_SERVICE_ACCOUNT_FILE")
    creds_file = os.getenv("GMAIL_CREDENTIALS_FILE")
    delegated = os.getenv("GMAIL_DELEGATED_USER")
    sender = os.getenv("SENDER_EMAIL")

    print(f"[Config] GMAIL_SERVICE_ACCOUNT_FILE: {svc_file or 'NÃO CONFIGURADO'}")
    print(f"[Config] GMAIL_DELEGATED_USER: {delegated or 'NÃO CONFIGURADO'}")
    print(f"[Config] GMAIL_CREDENTIALS_FILE: {creds_file or 'NÃO CONFIGURADO'}")
    print(f"[Config] SENDER_EMAIL: {sender or 'NÃO CONFIGURADO'}")
    print()

    if not (svc_file or creds_file):
        print("[ERROR] Nenhuma configuração de credenciais do Gmail encontrada.")
        print("Configure GMAIL_SERVICE_ACCOUNT_FILE ou GMAIL_CREDENTIALS_FILE no .env")
        exit(1)

    if not sender:
        print("[ERROR] SENDER_EMAIL não configurado.")
        exit(1)

    # Interatividade
    recipient = input("Destinatário (email): ").strip()
    if not recipient:
        recipient = "appnexxus.app@gmail.com"
        print(f"[Default] Usando: {recipient}")

    subject = input("Assunto (padrão 'Teste de Gmail'): ").strip()
    if not subject:
        subject = "Teste de Gmail API - Codex Operator"

    body = input("Corpo da mensagem (padrão genérico): ").strip()
    if not body:
        body = "Este é um email de teste enviado via Gmail API.\n\nCódigo-Operador: Automação MEI"

    print(f"\n[Info] Enviando para: {recipient}")
    print(f"[Info] Assunto: {subject}")
    print(f"[Info] De: {sender}")

    try:
        gmail = GmailAPI()
        result = gmail.send_message([recipient], subject, body, sender=sender)

        print(f"\n[Result] Status: {result.get('status')}")
        if result.get("id"):
            print(f"[Result] Message ID: {result.get('id')}")
        if result.get("error"):
            print(f"[Result] Erro: {result.get('error')}")

        print("\n" + "=" * 60)

    except Exception as e:
        logger.exception("Erro ao enviar: %s", e)
        print(f"\n[ERROR] Falha ao enviar: {e}")
        exit(1)
