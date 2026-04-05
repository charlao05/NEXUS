#!/usr/bin/env python3
"""
NEXUS — Setup automático do Stripe
====================================
Cria Products, Prices e Webhook Endpoint no Stripe.

Uso:
    python scripts/setup_stripe.py --key sk_live_SUA_CHAVE_AQUI
    python scripts/setup_stripe.py --key sk_test_SUA_CHAVE_AQUI   (modo teste)

O que este script faz:
  1. Cria 3 Products (Essencial, Profissional, Completo)
  2. Cria 3 Prices recorrentes (mensal, BRL)
  3. Cria Webhook Endpoint para receber eventos de pagamento
  4. Exibe as variáveis de ambiente para colar no Render/.env

Segurança:
  - A chave NÃO é salva em nenhum arquivo
  - O script é idempotente (pode rodar várias vezes sem duplicar)
"""

import argparse
import sys

try:
    import stripe
except ImportError:
    print("❌ Instale o Stripe SDK: pip install stripe")
    sys.exit(1)


# ── Definição dos planos ──────────────────────────────────────────────────
PLANS = [
    {
        "id": "essencial",
        "name": "NEXUS Essencial",
        "description": (
            "Plano Essencial — Contabilidade MEI, CRM (100 clientes), "
            "Cobrança automatizada e Agenda inteligente."
        ),
        "price_cents": 2990,  # R$ 29,90
        "features": [
            "Agente Contabilidade MEI (DAS, DASN, NF)",
            "CRM com até 100 clientes",
            "Agente de Cobrança automatizada",
            "Agente de Agenda inteligente",
            "300 mensagens/dia com IA",
            "Exportação de dados",
        ],
    },
    {
        "id": "profissional",
        "name": "NEXUS Profissional",
        "description": (
            "Plano Profissional — Tudo do Essencial + Assistente IA, "
            "500 clientes e 1.000 mensagens/dia."
        ),
        "price_cents": 5990,  # R$ 59,90
        "features": [
            "Tudo do Essencial",
            "Assistente IA para dúvidas e automações",
            "CRM com até 500 clientes",
            "1.000 mensagens/dia com IA",
            "Notificações completas (email + app)",
        ],
    },
    {
        "id": "completo",
        "name": "NEXUS Completo",
        "description": (
            "Plano Completo — Todos os agentes, clientes ilimitados, "
            "API completa e suporte dedicado."
        ),
        "price_cents": 8990,  # R$ 89,90
        "features": [
            "Tudo do Profissional",
            "Clientes e mensagens ilimitados",
            "Todos os agentes disponíveis",
            "API completa + integrações customizadas",
            "Suporte dedicado",
        ],
    },
]


# ── Eventos que o webhook precisa ouvir ───────────────────────────────────
WEBHOOK_EVENTS = [
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
    "customer.created",
    "customer.updated",
]


def find_existing_product(name: str) -> str | None:
    """Busca produto existente pelo nome (evita duplicação)."""
    products = stripe.Product.list(limit=100, active=True)
    for p in products.data:
        if p.name == name:
            return p.id
    return None


def find_existing_price(product_id: str, amount: int) -> str | None:
    """Busca price existente para um product (evita duplicação)."""
    prices = stripe.Price.list(product=product_id, active=True, limit=50)
    for p in prices.data:
        if (
            p.unit_amount == amount
            and p.currency == "brl"
            and p.recurring
            and p.recurring.interval == "month"
        ):
            return p.id
    return None


def create_products_and_prices() -> dict[str, str]:
    """Cria (ou encontra) Products e Prices. Retorna {plan_id: price_id}."""
    result = {}

    for plan in PLANS:
        print(f"\n{'─' * 50}")
        print(f"📦 Plano: {plan['name']}")

        # 1. Product
        existing_product_id = find_existing_product(plan["name"])
        if existing_product_id:
            product_id = existing_product_id
            print(f"   ✅ Product já existe: {product_id}")
        else:
            product = stripe.Product.create(
                name=plan["name"],
                description=plan["description"],
                metadata={"nexus_plan": plan["id"]},
                marketing_features=[
                    {"name": f} for f in plan["features"]
                ],
            )
            product_id = product.id
            print(f"   🆕 Product criado: {product_id}")

        # 2. Price
        existing_price_id = find_existing_price(product_id, plan["price_cents"])
        if existing_price_id:
            price_id = existing_price_id
            print(f"   ✅ Price já existe: {price_id}")
        else:
            price = stripe.Price.create(
                product=product_id,
                unit_amount=plan["price_cents"],
                currency="brl",
                recurring={"interval": "month"},
                metadata={"nexus_plan": plan["id"]},
            )
            price_id = price.id
            print(f"   🆕 Price criado: {price_id}")

        price_brl = plan["price_cents"] / 100
        print(f"   💰 R$ {price_brl:.2f}/mês")

        result[plan["id"]] = price_id

    return result


def create_webhook(backend_url: str) -> dict[str, str]:
    """Cria Webhook Endpoint no Stripe."""
    webhook_url = f"{backend_url.rstrip('/')}/api/auth/webhook/stripe"

    print(f"\n{'─' * 50}")
    print(f"🔔 Webhook: {webhook_url}")

    # Verificar se já existe
    existing = stripe.WebhookEndpoint.list(limit=50)
    for wh in existing.data:
        if wh.url == webhook_url and wh.status == "enabled":
            print(f"   ✅ Webhook já existe: {wh.id}")
            return {"webhook_id": wh.id, "webhook_secret": "(já configurado)"}

    webhook = stripe.WebhookEndpoint.create(
        url=webhook_url,
        enabled_events=WEBHOOK_EVENTS,
        description="NEXUS — Processamento de pagamentos e assinaturas",
        metadata={"app": "nexus"},
    )
    print(f"   🆕 Webhook criado: {webhook.id}")
    print(f"   🔑 Secret: {webhook.secret}")

    return {"webhook_id": webhook.id, "webhook_secret": webhook.secret}


def get_publishable_key() -> str:
    """Tenta obter a publishable key (não é possível via API, retorna instruções)."""
    return "(copie do Dashboard → dashboard.stripe.com/apikeys)"


def main():
    parser = argparse.ArgumentParser(
        description="NEXUS — Setup automático do Stripe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python scripts/setup_stripe.py --key sk_live_xxx
  python scripts/setup_stripe.py --key sk_test_xxx --backend-url http://localhost:8000
  python scripts/setup_stripe.py --key sk_live_xxx --backend-url https://nexus-api.onrender.com
        """,
    )
    parser.add_argument(
        "--key", required=True,
        help="Stripe Secret Key (sk_live_... ou sk_test_...)",
    )
    parser.add_argument(
        "--backend-url",
        default="https://nexus-api.onrender.com",
        help="URL do backend em produção (default: https://nexus-api.onrender.com)",
    )
    parser.add_argument(
        "--skip-webhook", action="store_true",
        help="Não criar webhook (apenas products e prices)",
    )

    args = parser.parse_args()

    # Validar chave
    if not args.key.startswith(("sk_live_", "sk_test_")):
        print("❌ Chave inválida. Deve começar com sk_live_ ou sk_test_")
        sys.exit(1)

    mode = "🔴 PRODUÇÃO" if args.key.startswith("sk_live_") else "🟡 TESTE"
    print(f"\n{'═' * 60}")
    print(f"  NEXUS — Setup Stripe ({mode})")
    print(f"{'═' * 60}")

    stripe.api_key = args.key

    # Testar conexão
    try:
        account = stripe.Account.retrieve()
        print(f"\n✅ Conectado: {account.get('business_profile', {}).get('name', account.id)}")
        print(f"   País: {account.country} | Moeda: {account.default_currency}")
    except stripe.AuthenticationError:
        print("❌ Chave inválida ou expirada. Verifique no dashboard.stripe.com/apikeys")
        sys.exit(1)

    # 1. Criar Products + Prices
    price_ids = create_products_and_prices()

    # 2. Criar Webhook
    webhook_info = {"webhook_secret": "(pular)"}
    if not args.skip_webhook:
        webhook_info = create_webhook(args.backend_url)

    # 3. Gerar output para configuração
    print(f"\n{'═' * 60}")
    print("  VARIÁVEIS DE AMBIENTE — Cole no Render / .env")
    print(f"{'═' * 60}")
    print()
    print(f"STRIPE_SECRET_KEY={args.key}")
    print(f"STRIPE_PUBLISHABLE_KEY={get_publishable_key()}")
    print(f"STRIPE_WEBHOOK_SECRET={webhook_info.get('webhook_secret', '')}")
    print(f"STRIPE_PRICE_ESSENCIAL={price_ids.get('essencial', '')}")
    print(f"STRIPE_PRICE_PROFISSIONAL={price_ids.get('profissional', '')}")
    print(f"STRIPE_PRICE_COMPLETO={price_ids.get('completo', '')}")
    print()

    # Gerar .env snippet para copiar
    print(f"{'─' * 60}")
    print("  FRONTEND (.env ou Render)")
    print(f"{'─' * 60}")
    print()
    print(f"VITE_STRIPE_PUBLISHABLE_KEY={get_publishable_key()}")
    print()

    print(f"{'═' * 60}")
    print("  ✅ Setup concluído!")
    print(f"{'═' * 60}")
    print()
    print("Próximos passos:")
    print("  1. Copie as variáveis acima para o Render (Environment)")
    print("  2. Copie a Publishable Key (pk_live_...) do Dashboard Stripe")
    print("  3. Faça redeploy no Render")
    print("  4. Teste um checkout no frontend")
    print()


if __name__ == "__main__":
    main()
