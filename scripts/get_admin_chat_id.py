"""
Aguarda uma mensagem no bot e captura o ADMIN_CHAT_ID.
Uso: python scripts/get_admin_chat_id.py
Envie qualquer mensagem para @appnexusapp_bot e este script captura automaticamente.
"""
import os
import time
import requests
import sys

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    print("ERRO: TELEGRAM_BOT_TOKEN não encontrado no .env")
    sys.exit(1)
BASE = f"https://api.telegram.org/bot{TOKEN}"

print("Aguardando mensagem no @appnexusapp_bot...")
print("Envie /start ou qualquer texto no Telegram.\n")

for attempt in range(60):  # 5 minutos max
    try:
        r = requests.get(f"{BASE}/getUpdates", timeout=10)
        data = r.json()
        if data.get("ok") and data.get("result"):
            msg = data["result"][0].get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            username = msg.get("from", {}).get("username", "?")
            first_name = msg.get("from", {}).get("first_name", "?")
            print(f"\n{'='*50}")
            print(f"CHAT_ID encontrado: {chat_id}")
            print(f"User: @{username} ({first_name})")
            print(f"{'='*50}")
            print(f"\nAdicione ao .env:")
            print(f"TELEGRAM_ADMIN_CHAT_ID={chat_id}")
            print(f"\nE no Render Dashboard:")
            print(f"TELEGRAM_ADMIN_CHAT_ID = {chat_id}")

            # Atualizar .env automaticamente
            env_path = ".env"
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "TELEGRAM_ADMIN_CHAT_ID=" in content:
                content = content.replace(
                    "TELEGRAM_ADMIN_CHAT_ID=",
                    f"TELEGRAM_ADMIN_CHAT_ID={chat_id}",
                )
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"\n.env atualizado automaticamente!")
            sys.exit(0)
    except Exception as e:
        print(f"  Erro: {e}")
    time.sleep(5)
    if attempt % 6 == 0 and attempt > 0:
        print(f"  ... aguardando ({attempt * 5}s)")

print("\nTimeout: nenhuma mensagem recebida em 5 minutos.")
sys.exit(1)
