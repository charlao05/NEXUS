# Runbook B — Execução

# 🔴 ALTERA PRODUÇÃO

## Pré-requisito, sem exceção

```
[ ] CHECKPOINT.md preenchido E assinado
```

**Se o checkpoint não estiver assinado, pare aqui.** Ele não é formalidade: é
onde estão os valores antigos que tornam o rollback possível, e a confirmação
de que o `DATABASE_URL` aponta para o Neon.

Voltar para: [`CHECKPOINT.md`](CHECKPOINT.md) ·
[`RUNBOOK_A_DIAGNOSTICO.md`](RUNBOOK_A_DIAGNOSTICO.md)

**Valores citados aqui:** [`PARAMETROS.md`](PARAMETROS.md) é a fonte. Os passos
repetem o valor literal por conveniência — **se divergir, o `PARAMETROS`
vence**, e a divergência é um defeito a corrigir.

---

## 🔴 Proibições durante toda a execução

1. **Não tocar em `DATABASE_URL`.** Nem para "corrigir".
2. **Não clicar em `Sync`, `Reapply blueprint` ou `Apply changes`.** Só a aba
   **Environment**.
3. **Não alterar variável fora da lista deste documento.**

---

## Formato de evidência — o mesmo do Runbook A

```
EVIDÊNCIA
  Origem:         <URL ou tela exata>
  Resultado:      <o que apareceu, literal>
  Como confirmei: <o que você fez para ter certeza>
```

---

# ⛑️ ROLLBACK IMEDIATO — leia ANTES de executar

Decore ou deixe esta seção aberta. Se você só for lê-la depois que algo der
errado, já perdeu tempo no pior momento possível.

```
SE O /health FALHAR APÓS UM SAVE

  1. NÃO salve de novo. NÃO tente "consertar por cima".
     Cada Save dispara um redeploy — empilhar Saves cria estados
     intermediários que ninguém consegue diagnosticar depois.

  2. Environment → restaure os valores da tabela "Valores antigos"
     do CHECKPOINT.md.

  3. UM único Save com tudo restaurado.
     Aguarde 2 a 5 minutos.

  4. Confira /health:
       voltou    → PARE. Reporte o que aconteceu antes de tentar de novo.
       não voltou → vá em Logs, copie o erro, e NÃO mexa em mais nada.
```

⚠️ **Nunca restaure pela metade.** Voltar a chave e deixar os price (ou o
contrário) produz `precos_ok: false` — estado pior que qualquer um dos dois
inteiros.

---

# B0 · Reativar o serviço — feito pelo dono, não delegado

**Este passo não é do executor nem de agente nenhum.** Envolve pagar ou remover
recurso, e a decisão foi tomada no [`CHECKPOINT.md`](CHECKPOINT.md), item 2.

Sem ele, **B1 e B2 não têm como rodar**: os dois terminam conferindo o
`/health`, e serviço suspenso não responde `/health`.

```
[ ] Executei a decisão do checkpoint (pagar OU remover o recurso)
[ ] curl https://api.nexxusapp.com.br/health responde JSON
[ ] "status": "ok"  ·  "database": "connected"
```

⚠️ **Se `database` vier `error` depois da reativação, PARE.** Não siga para o
B1 — mexer em Stripe com o banco fora torna qualquer diagnóstico posterior
inútil.

**COMO DESFAZER:** 🔴 **pagamento não se desfaz.** É por isso que a decisão fica
no checkpoint, antes, e não aqui.

---

# B1 · Stripe em modo live

**PRÉ:** o **B0** concluído — serviço **Live**. Se estiver suspenso, este passo
não roda.

**ONDE:** `https://dashboard.stripe.com` → depois
`https://dashboard.render.com` → `nexus-backend` → **Environment**

**O QUE FAZER**

1. Stripe → topo da tela → **DESLIGUE o "Test mode"**. Confirme antes de
   seguir.
2. **Developers → API keys** → linha "Secret key" → **Reveal live key** → use o
   **ícone de copiar** *(nunca selecione e arraste — é assim que se trunca)*
3. Render → `nexus-backend` → **Environment**
4. Edite as **quatro** variáveis abaixo
5. 🔴 **Um único Save, com as quatro já editadas**

**VALOR EXATO**

```
STRIPE_SECRET_KEY          = <a sk_live_ do passo 2>
STRIPE_PRICE_ESSENCIAL     = price_1TFtcdRwnNMZfuJ2Yfub1J0S
STRIPE_PRICE_PROFISSIONAL  = price_1TFteFRwnNMZfuJ2mi7OS4n2
STRIPE_PRICE_COMPLETO      = price_1TFtfmRwnNMZfuJ2PToTrk6O
```
*(parâmetros `PRICE_ESSENCIAL`, `PRICE_PROFISSIONAL`, `PRICE_COMPLETO` —
se divergirem do `PARAMETROS.md`, o `PARAMETROS` vence)*

⚠️ Existe uma **geração antiga** na conta (39,90 / 69,90 / 99,90) que continua
ativa e ainda é o `default_price` dos produtos. **Nunca escolha pelo nome do
produto — escolha pelo ID.**

**POR QUE UM SAVE SÓ (D-015):** o Stripe recusa chave live com price de teste.
Salvar em duas etapas deixa o sistema quebrado no intervalo — e cada Save
dispara um redeploy de 2 a 5 minutos, então o intervalo é real.

**COMO VERIFICAR**

Aguarde voltar a **Live**, depois `https://api.nexxusapp.com.br/health`:

```
config.stripe.autentica             →  true
config.stripe.motivo                →  contém "modo live"
config.stripe.precos_ok             →  true
config.stripe.cobranca_operacional  →  true   ← o que resume os dois
```

🔴 **É `precos_ok`**, não `precos_coerentes` — este último é o nome da função
no código e **não aparece no JSON**.

| Se veio | Significa |
|---|---|
| `autentica: false` + `chave REJEITADA` | **quase sempre truncamento** — refaça o passo 2 pelo ícone de copiar |
| `motivo: modo test` | esqueceu de desligar o Test mode antes de copiar |
| `precos_ok: false` | price de modo diferente da chave |
| `autentica: true` mas `cobranca_operacional: false` | **o pior caso**: parece certo e ninguém consegue pagar |
| `indeterminado: falha de rede` | blip — **não** é chave ruim, repita |

**COMO DESFAZER**
```
Restaurar:  as 4 variáveis, valores da tabela do CHECKPOINT
Como:       UM único Save com as 4 juntas
Esperar:    2 a 5 min
Validar:    /health → stripe.autentica: true, motivo "modo test"
```
🟢 Reversível **enquanto ninguém tiver pago**. Depois da primeira venda, voltar
para teste **não cancela a cobrança** — ela continua no Stripe e o NEXUS deixa
de enxergá-la. A partir daí isto deixa de ser rollback e vira migração.

---

# B2 · Webhook em modo live

**ONDE:** `https://dashboard.stripe.com/webhooks` *(Test mode **desligado**)*

**O QUE FAZER**

1. **Add endpoint**
2. URL — exatamente:
   ```
   https://api.nexxusapp.com.br/api/auth/webhook
   ```
   *(parâmetro `URL_WEBHOOK_STRIPE`)*

   ⚠️ **Não** é `/webhooks/stripe`, **não** é `/api/billing/webhook`. Essas
   duas **não existem**. Path errado = o cliente paga e não recebe acesso.
3. Selecione **os 6 eventos** *(parâmetro: eventos do webhook)*:
   ```
   checkout.session.completed
   invoice.paid
   invoice.payment_failed
   charge.refunded
   customer.subscription.updated
   customer.subscription.deleted
   ```
   Confirme que ficaram **6** selecionados. Evento a mais é ignorado; evento a
   menos significa que aquele efeito nunca acontece no NEXUS.
4. Salve → copie o **Signing secret** (`whsec_…`) pelo **ícone de copiar**
5. Render → Environment → `STRIPE_WEBHOOK_SECRET` = o `whsec_` → **Save**

**COMO VERIFICAR**

`/health` → `config.degradadas_faltando` **não** lista
`STRIPE_WEBHOOK_SECRET`.

⚠️ **Isso só prova que a variável existe — não que o webhook funciona.** A
prova está na validação final.

**COMO DESFAZER**
```
Desfazer:   Stripe → Webhooks → o endpoint → Disable  (NÃO Delete)
            Render → STRIPE_WEBHOOK_SECRET → valor do CHECKPOINT
Esperar:    2 a 5 min
Validar:    /health → degradadas_faltando sem STRIPE_WEBHOOK_SECRET
```
**Disable, não Delete** — desabilitado preserva o histórico de entregas, que é
o que você vai querer ler.

🟠 **Com o endpoint desabilitado, pagamento não ativa plano.** Se alguém pagar
nessa janela, o Stripe guarda o evento: reabilite e use **Resend** na entrega
que falhou. Do lado do NEXUS existe
`POST /api/admin/billing/resync-invoices`.

---

# B3 · E-mail — só se o diagnóstico apontou pendência

**PRÉ:** o passo A5 disse que o domínio está **Pending** ou que `EMAIL_FROM`
tem `@gmail.com`? Se estava tudo certo, **pule este passo**.

**O QUE FAZER**

1. Resend → **Domains** → adicione os registros **SPF** e **DKIM** no DNS de
   `nexxusapp.com.br` *(os valores exatos vieram do passo A5)*
2. Aguarde a verificação do Resend
3. Render → Environment:
   ```
   RESEND_API_KEY = re_…
   EMAIL_FROM     = NEXUS <contato@nexxusapp.com.br>
   ```

🔴 `EMAIL_FROM` **não pode** ser `@gmail.com` — o Resend recusa, e o e-mail não
sai nem com a chave certa.

**COMO VERIFICAR** — teste de **efeito**:

1. `https://app.nexxusapp.com.br` → login → **"Esqueceu a Senha?"**
2. Digite **seu e-mail de verdade**
3. Abra o Gmail — **inclusive a pasta Spam**

**O e-mail chegou, sim ou não?** É a única pergunta. Ler a chave no painel não
prova nada.

**COMO DESFAZER**
```
Restaurar:  RESEND_API_KEY e EMAIL_FROM, valores do CHECKPOINT
Esperar:    2 a 5 min
Validar:    Logs → nenhum CRITICAL de RESEND no boot
```
🟢 **Não desfaça o DNS.** SPF e DKIM não atrapalham nada se ficarem, e você vai
precisar deles na próxima tentativa.

⚠️ Sem `RESEND_API_KEY`, `forgot-password` responde **503** em vez de mentir
*"enviamos"* — é o comportamento correto, mas significa que **a recuperação de
senha fica indisponível** enquanto o rollback durar. Avise os cinco usuários.

---

# Validação final

## Parte 1 — o `/health`

```bash
curl -s https://api.nexxusapp.com.br/health
```

Todos os campos da tabela de `PARAMETROS.md` → *Campos do `/health` que
decidem*, no valor esperado.

## Parte 2 — a compra real

**Nenhum `/health` substitui isto.**

1. Crie uma conta nova em `https://app.nexxusapp.com.br`
2. Assine o **Essencial**
3. Confira **três coisas**:

| # | O quê | Onde |
|---|---|---|
| a | Cobrou **R$ 29,90** — não 39,90 | tela do checkout |
| b | Assinatura aparece em **live** | Stripe → Subscriptions |
| c | **O plano do usuário mudou** no NEXUS | perfil, ou `/api/auth/me` |

🔴 **O (c) é o que prova que o webhook chegou.** Se (a) e (b) passarem e (c)
falhar, o webhook não está funcionando — e é exatamente o cenário do pagamento
sem acesso.

⚠️ **`200` no painel do Stripe não prova nada.** O handler devolve 200 mesmo
quando falha (`_stripe_webhook_handler.py:602`, com comentário explícito), para
o Stripe não reenviar em duplicata. **Só o (c) prova.**

---

# Quando tudo passar

Atualize [`../PORTAO_O.md`](../PORTAO_O.md) para **✅ PRONTO PARA PRODUÇÃO** —
e só então os cinco usuários entram.
