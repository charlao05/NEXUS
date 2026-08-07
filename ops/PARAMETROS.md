# Parâmetros de ambiente — fonte única

**Todo valor acoplado à infraestrutura vive aqui.** Quando um price ID, uma URL
ou um nome de serviço mudar, edite **este arquivo** — não os runbooks.

## Regra de desempate

Os runbooks **repetem o valor literal** no passo onde ele é usado. Isso é
redundância proposital: quem executa não deveria ter que procurar, e
placeholder tipo `{{PRICE_ESSENCIAL}}` num prompt de agente é convite para ele
inventar o valor.

> **Se um valor no runbook divergir deste arquivo, ESTE ARQUIVO VENCE.**
> E a divergência é um defeito: corrija o runbook.

Cada parâmetro carrega **origem** e **verificado em**. A idade do valor fica
visível no próprio valor — é o que impede o documento de envelhecer em silêncio.

---

## Serviços

| Parâmetro | Valor | Origem | Verificado |
|---|---|---|---|
| `SERVICO_BACKEND` | `nexus-backend` | `render.yaml:4` | 02/08/2026 |
| `SERVICO_FRONTEND` | `nexus-frontend` | `render.yaml:110` | 02/08/2026 |
| `SERVICO_DB_RENDER` | `nexus-db` | `render.yaml:139` | 02/08/2026 |
| `PLANO_BACKEND` | `free` | `render.yaml:6` | 02/08/2026 |
| `PLANO_DB_RENDER` | `free` | `render.yaml:140` | 02/08/2026 |

⚠️ `SERVICO_DB_RENDER` é o Postgres **do Render** — **não é o banco de
produção**. Produção usa **Neon**. Ver `DATABASE_URL` abaixo.

## URLs

| Parâmetro | Valor | Origem | Verificado |
|---|---|---|---|
| `URL_API` | `https://api.nexxusapp.com.br` | `render.yaml:49` | 02/08/2026 |
| `URL_APP` | `https://app.nexxusapp.com.br` | `render.yaml:45` | 02/08/2026 |
| `URL_HEALTH` | `https://api.nexxusapp.com.br/health` | `render.yaml:21` | 02/08/2026 |
| `URL_WEBHOOK_STRIPE` | `https://api.nexxusapp.com.br/api/auth/webhook/stripe` | `auth.py:1563` | **07/08/2026** |

🔴 **Corrigido em 07/08/2026.** Este parâmetro dizia `/api/auth/webhook`
(`billing.py:269`). **O endpoint live registrado na conta usa
`/api/auth/webhook/stripe`** — medido na API (`we_1TLnQw…`, livemode, enabled, 6
eventos). As duas rotas existem e são equivalentes; a recomendação é que estava
desalinhada do que está em uso. **Trocar por trocar cria risco sem ganho.**

⚠️ **Não** é `/webhooks/stripe` nem `/api/billing/webhook` — essas não existem.
E existe um endpoint live apontando para `https://api.nexxusapp.com.br/billing/webhook`
(`we_1TCXbX…`), cuja **rota não existe**: falha entrega desde março. Ver E-048.

**Por que `/api/auth/` sendo o arquivo `billing.py`:** o router do `billing.py`
declara `prefix="/api/auth"` (`billing.py:14`) — o mesmo prefixo do `auth.py`
(`auth.py:464`). É o sombreamento registrado em **E-040**. Consequência prática:
**`/api/billing/…` não existe para nada.** Não deduza o path pelo nome do
arquivo.

## Stripe — price IDs

🔴 **MEDIDO EM 07/08/2026 — o ambiente de produção NÃO usa estes IDs.**

Os três Price IDs **atualmente configurados no Render** referenciam objetos que
existem **apenas em Test Mode**; a tentativa de uso com a chave live retorna
`No such price`. A `STRIPE_SECRET_KEY` **já é `sk_live_`**.

**Isso não é divergência documental — é falha operacional de cobrança**, e é o
estado misto que o **D-015** define como pior que qualquer um dos dois puros. Ver
**E-048**.

Geração **atual** (29,90 / 59,90 / 89,90) — **os corretos, a serem aplicados**:

| Parâmetro | Valor | Preço | Verificado |
|---|---|---|---|
| `PRICE_ESSENCIAL` | `price_1TFtcdRwnNMZfuJ2Yfub1J0S` | R$ 29,90 | 28/07/2026 |
| `PRICE_PROFISSIONAL` | `price_1TFteFRwnNMZfuJ2mi7OS4n2` | R$ 59,90 | 28/07/2026 |
| `PRICE_COMPLETO` | `price_1TFtfmRwnNMZfuJ2PToTrk6O` | R$ 89,90 | 28/07/2026 |

**Origem:** API do Stripe, conta `acct_1Sb8zuRwnNMZfuJ2` ("ChaMa"), todos
`livemode: true`, `recurring: month`.

⚠️ **Os price IDs não existem no repositório** — só no painel do Stripe e nas
variáveis do Render. O que o código tem são os **valores**:
`plan_limits.py:101,122,143` (`2990`, `5990`, `8990` centavos), e é só isso que
"bate". Se um ID mudar, **nenhum teste acusa** — a verificação é o
`cobranca_operacional` do `/health` e a compra real.

🔴 **Geração ANTIGA — NÃO USAR:**

| Produto | Price ID antigo | Preço |
|---|---|---|
| Essencial | `price_1TCliPRwnNMZfuJ2pR1VujPO` | R$ 39,90 |
| Profissional | `price_1TCllyRwnNMZfuJ2XgyN0APd` | R$ 69,90 |
| Completo | `price_1TClp7RwnNMZfuJ2c8KibMNR` | R$ 99,90 |

Ainda ativos na conta e ainda são o `default_price` dos produtos. **Nunca
escolha pelo nome do produto** — escolha pelo ID.

## Stripe — eventos do webhook

Exatamente estes seis, nem mais nem menos:

```
checkout.session.completed
invoice.paid
invoice.payment_failed
charge.refunded
customer.subscription.updated
customer.subscription.deleted
```

**Origem:** `_stripe_webhook_handler.py:495-502` (dict `_HANDLERS`) ·
Verificado 02/08/2026

Evento fora dessa lista chega e é **ignorado** (`status: "ignored"`). Evento
faltando = aquele efeito nunca acontece no NEXUS.

## Comprimentos esperados (detector de truncamento)

| Segredo | Prefixo | Comprimento típico |
|---|---|---|
| `STRIPE_SECRET_KEY` | `sk_live_` | ~107 caracteres |
| `STRIPE_WEBHOOK_SECRET` | `whsec_` | ~38 caracteres |
| `RESEND_API_KEY` | `re_` | ~36 caracteres |

⚠️ São **referências**, não regras — o Stripe pode mudar o formato. Servem para
comparar: um valor muito mais curto que o esperado é quase sempre truncamento.
**A prova real é o `/health`**, não o comprimento.

## Variáveis de ambiente por criticidade

**Origem:** `app/core/config_check.py:79-184` · Verificado 02/08/2026

| Nível | Variáveis | Efeito da ausência |
|---|---|---|
| **CRÍTICA** | `DATABASE_URL` · `JWT_SECRET` | **derruba o boot** em produção |
| **DEGRADADA** | `STRIPE_SECRET_KEY` · `STRIPE_PRICE_ESSENCIAL` · `STRIPE_PRICE_PROFISSIONAL` · `STRIPE_PRICE_COMPLETO` · `STRIPE_WEBHOOK_SECRET` · `RESEND_API_KEY` · `ADMIN_EMAILS` · `OPENAI_API_KEY` · `TAX_REGIME` | sobe, mas aparece em `/health` |
| **SILENCIOSA** | `USD_BRL_RATE` · `USD_BRL_UPDATED_AT` · `STRIPE_FEE_PERCENT` · `RENDER_COMPUTE_USD_PER_MIN` · `SENTRY_DSN` | sobe com warning |

### 🔴 `DATABASE_URL` — o parâmetro mais perigoso

```
Valor de produção:  postgresql://…neon.tech…   (só existe no painel do Render)
O que o blueprint diz:  fromDatabase: nexus-db  (render.yaml:28-31)
```

**Os dois divergem, e é assim que tem que ser.** Reaplicar o blueprint troca o
banco por um **vazio** — e o sistema **não cai**: `/health` responde
`database: connected`, a aplicação sobe, os dados somem de vista.

**Regra (D-014):** nunca `Sync` / `Reapply blueprint` em produção. Trabalhe só
pela aba **Environment**.

## Campos do `/health` que decidem

**Origem:** `main.py:271` + `config_check.py:511` · Verificado 02/08/2026

| Campo | Valor esperado | Se diferente |
|---|---|---|
| `status` | `"ok"` | `degraded` = banco inacessível |
| `database` | `"connected"` | `error` = `DATABASE_URL` errada ou banco fora |
| `config.status` | `"ok"` | `critical` / `degraded` / `ok_with_warnings` |
| `config.criticas_faltando` | `[]` | o boot nem deveria ter subido |
| `config.degradadas_faltando` | `[]` | **lista os nomes** que faltam |
| `config.stripe.autentica` | `true` | a chave **não cobra** |
| `config.stripe.motivo` | contém `"modo live"` | `modo test` = Test mode ligado |
| `config.stripe.precos_ok` | `true` | price de modo diferente da chave |
| `config.stripe.cobranca_operacional` | `true` | **o campo que resume**: `autentica` **E** `precos_ok` |
| `config.automacao_web.disponivel` | `true` | chromium ausente — **não bloqueia** |

🔴 **O campo chama-se `precos_ok`, não `precos_coerentes`.**
`stripe_precos_coerentes()` é o nome da **função** (`config_check.py:408`); o
JSON expõe `precos_ok` (`config_check.py:545`). Procurar pelo nome errado no
`/health` faz o executor concluir "o campo não existe, deve estar quebrado".

💡 **Se for olhar um campo só, olhe `cobranca_operacional`**
(`config_check.py:547`). Ele é `autentica and precos_ok` — chave boa com price
errado dá `autentica: true` e **`cobranca_operacional: false`**, que é
exatamente o estado em que o cliente não consegue pagar.

## Painéis

| Onde | URL |
|---|---|
| Render | `https://dashboard.render.com` |
| Stripe | `https://dashboard.stripe.com` |
| Neon | `https://console.neon.tech` |
| Resend | `https://resend.com` |

---

## Como manter este arquivo

1. Mudou um valor de infraestrutura? **Edite aqui primeiro.**
2. Depois procure o valor literal nos runbooks e atualize — a divergência é
   defeito, não tolerância.
3. Atualize a coluna **Verificado**. Valor sem data recente é valor suspeito.

**Nada aqui é segredo.** Chaves e connection strings **não entram** neste
arquivo — só nomes, IDs públicos, URLs e formatos esperados.
