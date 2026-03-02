"""Exemplo de teste real da integração WhatsApp."""

import json
from dotenv import load_dotenv
from backend.integrations.whatsapp_api import WhatsAppAPI

# Carregar variáveis do .env
load_dotenv()

if __name__ == "__main__":
    # Teste envio de mensagem de texto simples
    api = WhatsAppAPI()

    recipient = "+1 555 632 2287"  # Seu número de teste
    message = """Olá! 👋

Teste de integração WhatsApp do NEXUS ✅

Esta mensagem foi gerada automaticamente para validar a integração com a API do WhatsApp Business.

Você pode:
1. Enviar instruções de notas fiscais
2. Mensagens de cobrança automática
3. Notificações de atendimento
4. E muito mais!

Qualquer dúvida, entre em contato. 📱"""

    print("Enviando mensagem para:", recipient)
    print("-" * 50)
    result = api.send_text_message(recipient, message)
    print("Resposta da API:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
