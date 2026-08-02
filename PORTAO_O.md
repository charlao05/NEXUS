# Portão O — Operação

## Resultado

# ⛔ AINDA NÃO

**Data:** 02/08/2026

Tudo que depende de infraestrutura, conta paga e configuração de painel.
**Nenhum item aqui se prova por teste** — por isso não está em
[`PORTAO_A.md`](PORTAO_A.md), que já **PASSOU**.

> Se a resposta para "por que não subiu?" for *"falta pagar"*, *"falta a
> chave"* ou *"falta configurar"*, o item é deste documento. Sem essa
> separação, a equipe diz "não passou no Portão A" quando o que falta é uma
> fatura do provedor.

---

## Bloqueia tudo

### 1 · Render ativo
```
Estado:  ⛔ SUSPENSO por inadimplência (E-034)
Efeito:  api. e app.nexxusapp.com.br respondem "This service has been suspended"
Onde:    dashboard.render.com/billing
Verificar: curl -s https://api.nexxusapp.com.br/health   → {"status":"ok"}
```
**Enquanto isto durar, nada abaixo se verifica** — nem o PITR, nem o Stripe,
nem o e-mail. E nenhum usuário entra.

### 2 · Stripe em modo live
```
Estado:  ⛔ chaves de TESTE em produção (E-029)
Falta:   STRIPE_SECRET_KEY = sk_live_…
         STRIPE_PRICE_ESSENCIAL    = price_1TFtcdRwnNMZfuJ2Yfub1J0S
         STRIPE_PRICE_PROFISSIONAL = price_1TFteFRwnNMZfuJ2mi7OS4n2
         STRIPE_PRICE_COMPLETO     = price_1TFtfmRwnNMZfuJ2PToTrk6O
Onde:    Render → nexus-backend → Environment (as 4 num Save só)
Verificar: /health → config.stripe.autentica: true, modo "live"
```
⚠️ Conferir caractere a caractere: um price ID errado cobra o valor errado de
um cliente real, e o sistema não tem como saber.

### 3 · Webhook do Stripe em live
```
Estado:  ⛔ não confirmado
URL:     https://api.nexxusapp.com.br/api/auth/webhook
Eventos: checkout.session.completed · invoice.paid · invoice.payment_failed
         charge.refunded · customer.subscription.updated/deleted
Falta:   STRIPE_WEBHOOK_SECRET = whsec_… (do endpoint LIVE)
Verificar: uma compra real → o plano do usuário muda no NEXUS
```
🔴 **É o pior modo de falha com cliente real:** sem o webhook live, o cliente
paga e **não recebe acesso**. O código está testado (`604a207`); falta a
configuração.

**Este item é o `SKIPPED` nº 1 da suíte** — `test_webhook_recusa_assinatura_
invalida` pula porque não há `STRIPE_WEBHOOK_SECRET`. A fronteira A/O
aparecendo sozinha.

### 4 · Backup do banco — PITR do Neon
```
Estado:  ⛔ NUNCA VERIFICADO
Perguntas: o plano atual inclui point-in-time recovery?
           qual a retenção, em dias?
Onde:    console.neon.tech → projeto nexus → Settings
Se NÃO incluir: aí sim vira trabalho de engenharia (dump agendado)
```
A metade do **usuário** já existe e está testada — `/api/auth/export-my-data`,
5 testes, Portão A. Esta é a metade do **banco**.

### 5 · E-mail transacional
```
Estado:  ⛔ não verificado nesta rodada
Falta:   RESEND_API_KEY (re_…) · EMAIL_FROM @nexxusapp.com.br
         domínio verificado no Resend (SPF/DKIM no DNS)
Verificar: recuperação de senha → o e-mail CHEGA na inbox
```
⚠️ `EMAIL_FROM` com default `@gmail.com` **não é aceito** pelo Resend. Chave
configurada sem domínio verificado não resolve nada.

**Este é o `SKIPPED` nº 2** — `test_forgot_password_integracao` pula porque o
pacote `resend` não está instalado no ambiente.

---

## Não bloqueia o piloto, mas registrar

### 6 · Domínio, DNS e HTTPS
```
Estado:  ✅ funcionavam antes da suspensão
Verificar: https://app.nexxusapp.com.br carrega com cadeado
```

### 7 · Monitoramento
```
Sentry:  ✅ ativo antes da suspensão (/health → sentry: "active")
Falta:   alerta que avise VOCÊ quando /health parar de responder
         (hoje a descoberta seria por um usuário reclamando)
```

### 8 · Disaster Recovery
```
Estado:  ⛔ NUNCA DISCUTIDO — e é diferente de backup
```
Backup responde *"os dados existem em outro lugar?"*. DR responde *"em quanto
tempo o serviço volta, e quem faz?"*. Para cinco usuários em sete dias, o risco
é aceitável — mas fica escrito, não esquecido.

---

## Ordem recomendada

1. **Render** — sem isto nada mais se verifica
2. **Stripe live** (4 envs num Save só) + **webhook live**
3. **PITR do Neon** — pergunta de painel; se não existir, vira engenharia
4. **E-mail** — teste de efeito: o e-mail chega ou não chega
5. Então: **os cinco usuários entram**

---

## O que este documento NÃO é

Não é lista de melhorias. Item entra aqui só se **impedir cinco pessoas de
usar o produto por sete dias** — o mesmo filtro do Portão A, aplicado ao que
não é código.
