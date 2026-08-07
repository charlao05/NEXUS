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

## Critérios de saída

| # | Bloqueador | Estado | Onde se resolve |
|---|---|---|---|
| 1 | **Render ativo** | ⛔ suspenso por inadimplência (E-034) | Runbook A, passo A2 (diagnóstico) → decisão no checkpoint → **Runbook B, passo B0** (o dono executa) |
| 2 | **Stripe em modo live** | ⛔ chaves de teste em produção (E-029) | Runbook B, passo B1 |
| 3 | **Webhook live** | ⛔ não confirmado | Runbook B, passo B2 |
| 4 | **Backup do banco (PITR do Neon)** | ⛔ nunca verificado | Runbook A, passo A4 |
| 5 | **E-mail transacional** | ⛔ não verificado | Runbook A, passo A5 → Runbook B, passo B3 |

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
   ([`ops/PARAMETROS.md`](ops/PARAMETROS.md))
2. **Uma compra real de R$ 29,90 que muda o plano do usuário no NEXUS**

O `/health` prova configuração. Só a compra prova a cadeia inteira — e
`200` no painel do Stripe **não conta**, porque o handler devolve 200 mesmo
quando falha.

---

## O que este documento NÃO é

Não é lista de melhorias. Item entra aqui só se **impedir cinco pessoas de usar
o produto por sete dias** — o mesmo filtro do Portão A, aplicado ao que não é
código.
