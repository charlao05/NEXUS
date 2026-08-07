# Portão O — Operação

## Resultado

# ⛔ AINDA NÃO

**Data:** 03/08/2026

Tudo que depende de infraestrutura, conta paga e configuração de painel.
**Nenhum item aqui se prova por teste** — por isso não está em
[`PORTAO_A.md`](PORTAO_A.md), que já **PASSOU**.

> Se a resposta para *"por que não subiu?"* for **"falta pagar"**, **"falta a
> chave"** ou **"falta configurar"**, o item é deste portão. Sem essa
> separação, a equipe diz "não passou no Portão A" quando o que falta é uma
> fatura do provedor.

---

## Como executar

Este documento é **o portão** — estado e critérios. O procedimento vive em
`ops/`, separado em cinco etapas:

```
 1. DIAGNÓSTICO   ops/RUNBOOK_A_DIAGNOSTICO.md    🔵 só leitura
        ↓
 2. AUTORIZAÇÃO   ops/CHECKPOINT.md               ✍️  assinado pelo dono
        ↓
 3. EXECUÇÃO      ops/RUNBOOK_B_EXECUCAO.md       🔴 altera produção
        ↓
 4. ROLLBACK      (dentro do B, por procedimento)
        ↓
 5. VALIDAÇÃO     (fim do B — /health + compra real)
```

**Valores de ambiente** (price IDs, URLs, nomes de serviço):
[`ops/PARAMETROS.md`](ops/PARAMETROS.md) — fonte única. Quando algo mudar na
infraestrutura, edite lá, não nos runbooks.

⚠️ **O Runbook B não roda sem o checkpoint assinado.** Não é formalidade: é
onde ficam os valores antigos que tornam o rollback possível.

---

## Estado medido — 07/08/2026

O diagnóstico (Runbook A) + verificação na API da Stripe substituíram a lista de
"5 bloqueadores" por algo mais factual. **Metade já está confirmada.**

### ✅ Confirmado

| | Como se sabe |
|---|---|
| Produção aponta para **Neon**, não para `nexus-db` | `DATABASE_URL` contém `neon.tech` |
| Origem da cobrança **identificada** | $25,56 de datastores **deletados** de `apocalipse`/`alinha` + $0,94 de cron. **NEXUS Free = $0,00** |
| `STRIPE_SECRET_KEY` **já é live** | lida no painel |
| **Webhook correto já existe** | `we_1TLnQw…` · livemode · enabled · os 6 eventos (E-048) |
| Endpoint **morto** identificado | `we_1TCXbX…` → `/billing/webhook`, rota inexistente (E-048) |
| **Resend verificado** | domínio `Verified`, `EMAIL_FROM` sem gmail |
| **Zero assinaturas live** | `GET /v1/subscriptions` → `[]` (E-048) |
| `nexus-db` **não é produção** | e será deletado em 21/08/2026 |

### ⛔ Ainda precisa de ação ou verificação

| # | Item | Onde |
|---|---|---|
| 1 | **Corrigir os 3 price IDs** — hoje apontam para test mode com chave live | Runbook B, **B1** |
| 2 | **Confirmar o `whsec_`** do endpoint correto | Runbook B, **B2** |
| 3 | **Desabilitar** o webhook morto | Runbook B, **B2** |
| 4 | **Render ativo** — decidir a fatura | checkpoint → **B0** (o dono) |
| 5 | **PITR do Neon** — *History window* = **6 horas**, plano Free | checkpoint, item 4 |
| 6 | **Country** da conta Stripe | Prompt A, **A6.4** *(relatório cortou)* |
| 7 | **Pix ativo?** em Payment methods | Prompt A, **A6.5** *(relatório cortou)* — decide o **DIV-001** |
| 8 | **Rotação** das 4 credenciais expostas | decisão do dono (E-048) |

🔴 **O item 1 não é configuração pendente — é falha operacional de cobrança.**
Com chave live e price de test mode, a Stripe responde `No such price`: ninguém
consegue assinar. Só não virou incidente porque o serviço está suspenso.

⚠️ **Os itens 6 e 7 não pertencem a este portão.** Decidem o `DIV-001` (a
promessa de PIX na página de preços) e estão aqui só porque a mesma ida ao painel
os resolve.

### Não bloqueiam, mas registrado

| Item | Estado |
|---|---|
| Domínio, DNS, HTTPS | ✅ funcionavam antes da suspensão |
| Monitoramento (Sentry) | ✅ ativo — **falta** alerta que avise quando `/health` parar |
| **Disaster Recovery** | ⛔ **nunca discutido** |
| **Divergências produto × implementação** | 📋 registradas em [`docs/DIVERGENCIAS.md`](docs/DIVERGENCIAS.md) — **DIV-001** (PIX no addon) e **DIV-004** abertas |

⚠️ **Divergências não são bloqueadores deste portão, e o registro delas fica
fora daqui de propósito.** Este documento responde *"posso colocar em
produção?"*. O `DIVERGENCIAS.md` responde *"o produto comunica exatamente o que
ele faz?"* — pergunta que continua valendo muito depois deste portão fechar.

**DR é diferente de backup.** Backup responde *"os dados existem em outro
lugar?"*; DR responde *"em quanto tempo o serviço volta, e quem faz?"*. Para
cinco usuários em sete dias o risco é aceitável — fica **escrito**, não
esquecido.

---

## A prova de que a fronteira A/O é real

Dos **521 testes** do Portão A, os **dois únicos `SKIPPED`** são:

```
test_caminho_do_dinheiro.py::test_webhook_recusa_assinatura_invalida
  → STRIPE_WEBHOOK_SECRET ausente          (bloqueador 3)

test_forgot_password_integracao.py
  → pacote 'resend' nao instalado          (bloqueador 5)
```

**A suíte de engenharia só não consegue verificar aquilo que não é
engenharia.** Quando os bloqueadores 3 e 5 fecharem, os dois deixam de pular.

---

## O que fecha este portão

**Duas provas, e a segunda não se substitui:**

1. `/health` com todos os campos no valor esperado
   ([`ops/PARAMETROS.md`](ops/PARAMETROS.md)) — **incluindo
   `stripe.cobranca_operacional: true`**
2. **Uma compra real de R$ 29,90 que muda o plano do usuário no NEXUS**

O `/health` prova configuração. Só a compra prova a cadeia inteira — e
`200` no painel do Stripe **não conta**, porque o handler devolve 200 mesmo
quando falha.

🔴 **`cobranca_operacional` entrou na lista por medição, não por precaução.** É
exatamente o campo que hoje diria `false` enquanto `autentica` diz `true`
(E-048). Trocar os preços sem conferir esse campo é repetir o erro que o
princípio **#7** descreve: aceitar sinal parcial como prova de saúde.

---

## O que este documento NÃO é

Não é lista de melhorias. Item entra aqui só se **impedir cinco pessoas de usar
o produto por sete dias** — o mesmo filtro do Portão A, aplicado ao que não é
código.
