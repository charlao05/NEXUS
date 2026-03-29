#!/usr/bin/env python
"""Script para configurar Gmail no Google Cloud Shell.

Para usar em produção no Cloud Shell com Service Account autenticada.

Execução no Cloud Shell:
python -m src.integrations.setup_gmail_cloudshell
"""

import os
import json


def setup_gmail_cloudshell():
    try:
        from google.auth import default
    except ImportError:
        print("[ERROR] google-auth não está instalado.")
        return False

    print("[Info] Detectando credenciais do Cloud Shell...")

    try:
        # Usar as credenciais padrão do Cloud Shell
        creds, project_id = default(
            scopes=["https://www.googleapis.com/auth/gmail.send"]
        )

        # Salvar credenciais em arquivo JSON
        output_file = "gmail_cloudshell_creds.json"
        creds_data = {
            "type": "authorized_user",
            "client_id": getattr(creds, "client_id", ""),
            "client_secret": getattr(creds, "client_secret", ""),
            "refresh_token": getattr(creds, "refresh_token", ""),
            "token": getattr(creds, "token", ""),
            "project_id": project_id,
        }

        with open(output_file, "w") as f:
            json.dump(creds_data, f, indent=2)

        print(f"\n[Success] Credenciais configuradas: {os.path.abspath(output_file)}")
        print("\nAdicione no seu .env:")
        print(f'GMAIL_CREDENTIALS_FILE="{os.path.abspath(output_file)}"')
        print('SENDER_EMAIL="appnexxus.app@gmail.com"')
        print('GOOGLE_CALENDAR_ID="primary"')
        print()
        return True

    except Exception as e:
        print(f"[ERROR] Falha ao configurar: {e}")
        print("\n[Alternativa] Use Service Account JSON da Google Cloud Console:")
        print("1. Vá para: https://console.cloud.google.com/iam-admin/serviceaccounts")
        print("2. Selecione uma Service Account")
        print("3. Crie uma chave JSON")
        print("4. Configure no .env como GMAIL_SERVICE_ACCOUNT_FILE")
        return False


if __name__ == "__main__":
    success = setup_gmail_cloudshell()
    exit(0 if success else 1)
