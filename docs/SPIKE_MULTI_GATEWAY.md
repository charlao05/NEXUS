# Spike Arquitetural — Multi-gateway de pagamentos

# 📄 DOCUMENTO. NÃO É IMPLEMENTAÇÃO.

**Nenhuma linha de código, nenhuma refatoração, nenhuma migration sai deste
documento.** Ele existe para que o conhecimento adquirido numa pesquisa não
precise ser adquirido de novo daqui a seis meses.

**Data:** 03/08/2026 · **Decisão que o originou:**
[`DECISOES.md` → D-017](../DECISOES.md) · **Evidência:** E-046

> A decisão vigente é **manter Stripe**. Este documento descreve o que *seria*
> preciso, **se e quando** um dos gatilhos do D-017 ocorrer. Ler isto como
> autorização para começar é o erro que ele existe para evitar.

---

## 1 · Como funcionaria

**Adicionar um provedor, não substituir.** A diferença não é de estilo, é de
risco: substituir obriga a migrar a base existente — reautorização de meio de
pagamento cliente a cliente, com perda garantida de parte deles. Adicionar
permite que clientes novos entrem pelo provedor novo enquanto os antigos
continuam onde estão.

```
                 ┌──────────────────────────┐
   domínio  ───► │  Billing do NEXUS        │  planos, ciclos, status
   (nosso)       │  IDs internos            │  NÃO conhece provedor
                 └───────────┬──────────────┘
                             │  Provider Interface
                 ┌───────────┴──────────────┐
                 ▼                          ▼
          adapter Stripe            adapter Mercado Pago
```

A regra que sustenta tudo: **o domínio usa IDs internos.** O ID do provedor é um
dado de integração, não a chave do negócio. Hoje é o contrário — ver §4.

---

## 2 · O que precisaria ser abstraído

| Componente | Onde vive hoje |
|---|---|
| **Provider Interface** | não existe — `auth.py` chama `stripe.checkout.Session.create` direto |
| **Checkout** | `auth.py:1242` (vivo) · `billing.py:90` (sombreado, E-040) · `Pricing.tsx` |
| **Webhooks** | `_stripe_webhook_handler.py` — `_HANDLERS`, 6 eventos |
| **Assinaturas** | `_billing_helpers.py`, `database/models.py` |
| **Eventos / idempotência** | tabelas `stripe_events`, `WebhookHit` |
| **Saúde / config** | `config_check.py` — `stripe_autentica`, `precos_ok`, `cobranca_operacional` |

Contrato mínimo: `criarCliente` · `criarAssinatura` · `cobrarFatura` ·
`cancelarAssinatura` · `atualizarMeioDePagamento` · `traduzirEvento`.

⚠️ **`traduzirEvento` é o difícil.** Os 6 eventos da Stripe não têm equivalente
1:1 no `preapproval` do Mercado Pago. A interface precisa ser desenhada sobre o
que o NEXUS *precisa saber* (assinou · pagou · falhou · cancelou · estornou), não
sobre o vocabulário de nenhum dos dois.

## 2.1 · O que NÃO deve ser abstraído

Nem tudo precisa virar interface. **Abstrair sem segundo implementador é o
retrabalho que o `ARCH_PRINCIPLES.md` existe para evitar.**

| Não abstrair | Por quê |
|---|---|
| Regras tributárias | são do domínio fiscal brasileiro, não do provedor |
| CRM | clientes do usuário ≠ clientes do gateway |
| Autenticação | não tem relação com cobrança |
| Usuários | `User` é a raiz do tenant, não um registro de billing |

---

## 3 · O custo dominante: o banco

**As colunas de provedor têm `unique=True`:**

```
User.stripe_customer_id              models.py:253    unique
Subscription.stripe_subscription_id  models.py:349    unique
InvoicePayment.stripe_invoice_id     models.py:1102   unique
```

**Uma coluna única chamada `stripe_*` não comporta um ID de outro provedor.**

Isso é o achado mais concreto deste spike: abstrair o provedor **não é**
principalmente escrever uma interface. É migrar para pares
`(provider, external_id)`, com unicidade **composta** — mudança de schema, em
tabelas que guardam o histórico financeiro, com dados de produção dentro.

Tabelas afetadas: `users` · `subscriptions` · `invoice_payments` ·
`stripe_events` (o nome também é do provedor) · `webhook_hits`.

⚠️ **Ordem obrigatória, se um dia acontecer:** adicionar as colunas novas →
preencher com `provider='stripe'` → trocar as constraints → só então remover as
antigas. Cada passo é um deploy separado, com rollback próprio (D-016).

---

## 4 · Recursos do Mercado Pago — e o que cada um não resolve

| Recurso | Resolve | **Não** resolve |
|---|---|---|
| Pix avulso | pagamento único, taxa baixa | recorrência — não serve para assinatura |
| **Pix Automático** | **churn involuntário de cartão** — o motivo real | conversão; exige o cliente autorizar no app do banco |
| `preapproval` | assinatura recorrente | pró-rata em upgrade/downgrade — precisa ser modelado no backend |
| Split | marketplace de serviços | nada do produto atual |
| Wallet / conta digital | custo de cash-in/out | nada de billing |

**Pix Automático é o único item genuinamente estratégico.** Cartão de MEI expira,
falha, estoura limite — e o cliente que queria continuar pagando sai sem querer.
É o que o gatilho (1) do D-017 mede.

---

## 5 · Impacto

**Backend** — Provider Interface, adapter, tradução de eventos, idempotência por
provedor, `config_check` por provedor, rotas de checkout, `admin/resync-invoices`.

**Frontend** — `Pricing.tsx` (escolha de meio de pagamento), telas de assinatura
e de atualização de método, e o fluxo do Pix, que **não é redirect**: o cliente
sai do site, abre o banco, autoriza, e volta — ou não volta.

**Infraestrutura** — novas envs, novo webhook, `ops/PARAMETROS.md` passa a ter
duas famílias de segredo, `/health` precisa responder por provedor.

## 5.1 · Custo oculto — a operação

O que não aparece em nenhum diagrama e consome mais tempo que o código:

migração de clientes · comunicação com a base · alteração de links de pagamento ·
suporte durante a transição · **conciliação financeira com duas fontes** ·
cancelamentos · **reautorização de meio de pagamento** · documentação ·
treinamento · monitoramento · dashboards · runbooks.

⚠️ **A reautorização é o item que perde receita.** Nenhum provedor transfere
autorização de cartão para outro. Trocar de gateway significa pedir a cada
cliente pagante que cadastre o cartão de novo — e uma fração não faz.

---

## 6 · Esforço qualitativo

Ancorado em medição, não em impressão:

```
457 linhas com referência a Stripe
 12 arquivos-fonte + 10 de teste
  6 handlers de webhook
  5 tabelas com identificadores de provedor
  1 runbook operacional (ops/) inteiro
```

**Alto**, e a parte cara não é a interface — é o schema (§3) e a operação (§5.1).

**O agravante que o número não mostra:** o caminho do dinheiro é o subsistema que
quebrou produção **duas vezes** em uma semana (E-042: pia derrubou o webhook ·
E-043: `billing.py` devolvia 500 antes disso). Reescrevê-lo é reabrir a área de
maior taxa de defeito histórico do projeto.

---

## 7 · Riscos técnicos

| Risco | Por quê |
|---|---|
| **Dupla fonte de verdade** | duas assinaturas ativas para o mesmo usuário, uma em cada provedor |
| **Idempotência por provedor** | `stripe_events` garante idempotência de um. Dois provedores exigem chave composta, ou um evento repetido de MP passa |
| **Conciliação** | fechamento financeiro passa a somar duas origens com formatos e prazos diferentes |
| **Divergência de estados** | `past_due` da Stripe não tem o mesmo significado que `pending` do `preapproval` |
| **Reautorização** | ver §5.1 — perda de receita, não de código |
| **Webhook duplo** | duas superfícies não autenticadas por sessão; a escotilha `sem_tenant` precisaria valer para as duas |

---

## 8 · Quando reabrir

Os gatilhos vivem em **[`DECISOES.md` → D-017](../DECISOES.md)** e não são
copiados aqui de propósito — duas cópias divergem, e a que alguém lê primeiro
vence.

Em resumo: churn involuntário medido · demanda registrada no CRM · mudança
estratégica do produto · mudança de capacidade ou condição comercial dos
provedores.

---

## 9 · O que este spike NÃO avaliou

Disponibilidade e SLA do Mercado Pago · histórico de indisponibilidade ·
qualidade do suporte · estabilidade da API · risco regulatório · estratégia
internacional · múltiplas moedas · Open Finance · custos operacionais de
conciliação.

**Silêncio aqui não é aprovação.** Se algum desses virar critério de decisão, ele
precisa ser pesquisado — este documento não responde por ele.
