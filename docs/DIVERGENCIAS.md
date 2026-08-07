# Divergências abertas — promessa × implementação

# ⏳ DOCUMENTO TRANSITÓRIO

**Este arquivo tem fim previsto.** Ele existe porque a pergunta *"o produto
promete algo que não entrega?"* ainda não tem outra casa — não porque
divergência seja um domínio próprio.

**O quadro do [D-018](../DECISOES.md), preenchido:**

| Campo | |
|---|---|
| **Objetivo** | o produto promete algo que a implementação não entrega? |
| **Critério de criação** | existe divergência aberta e nenhum documento a responde |
| **Duplicação** | nenhum documento responde isso hoje |
| **Critério de encerramento** | a Matriz de Funcionalidades existir **ou** zerarem as divergências abertas |
| **Documento sucessor** | Matriz de Funcionalidades — divergência vira **estado de uma funcionalidade** |

⚠️ **O critério de encerramento não foi preenchido quando este arquivo nasceu.**
Ele começou com cinco categorias inventadas a partir de quatro observações — três
sem nenhuma instância — e com dois itens encerrados ocupando espaço. Isto é o que
sobrou depois de aplicar o D-018.

🔴 **O gatilho de aposentadoria não vale para item exigido externamente.** Se
algum item vier a ser exigido por obrigação legal, regulatória, contratual ou de
auditoria, ele **deixa de ser transitório** — migra para registro permanente em
vez de sumir com o arquivo. Foi o que aconteceu com a exportação LGPD (**E-047**).

## Regras

1. **Somente itens abertos.** Item encerrado **sai daqui** — não vira histórico
   local. O histórico já existe em teste, commit e registro de evidência;
   duplicá-lo aumenta manutenção sem acrescentar informação.
2. **Toda promessa precisa de fonte citável** — `arquivo:linha`. *"O produto dá a
   entender"* é interpretação, não promessa.
3. **Todo item precisa de critério de encerramento**, e ele tem **dois lados**:
   cumprir a promessa **ou** corrigir a comunicação. Escolher é decisão de
   produto, não de engenharia.
4. **Nenhuma categoria antes de existir instância.** Sem taxonomia antecipada.

---

## DIV-001 · PIX prometido no addon, checkout oferece só cartão

**Aberto** · descoberto em **E-046** · relacionado: **D-017**

**Promessa** — `Pricing.tsx:359-366`, bloco do addon de R$ 12,90 (compra única):

> "💳 Cartão ou **PIX** — QR Code válido por 30 min"

**Implementação** — `auth.py:1523-1536`:

```python
payment_method_types=["card"],   # :1524
mode="payment",                  # :1536
```

**Impacto:** comercial e jurídico — afirmação sobre condição de pagamento numa
página de venda, para um público em que Pix é o meio mais familiar.

**Por que é resolvível:** o addon é `mode="payment"`, e **Pix avulso é suportado
pela Stripe nesse modo**. O que bloqueia é a linha `payment_method_types`, que
ainda desliga os métodos dinâmicos do painel.

⚠️ **Não confundir com a restrição de assinatura.** Pix em `mode="subscription"`
exige Pix Automático, indisponível para conta Stripe BR nesta data (D-017). Vale
para os planos, **não** para este addon.

**Pendente — duas leituras de painel:**

```
dashboard.stripe.com/settings/account          → Country: ______
dashboard.stripe.com/settings/payment_methods  → Pix: [ativo/inativo/indisponível]
```

| Country | Pix | Ação |
|---|---|---|
| BR | ativo | **cumprir a promessa** — `["card","pix"]` em `auth.py:1524` |
| BR | inativo | **alinhar a copy** — `Pricing.tsx:365` |
| ≠ BR | qualquer | reabrir D-017 — Pix Automático estaria disponível |

**Critério para encerrar:** página e checkout do addon comunicam o mesmo conjunto
de meios de pagamento, com teste que falhe se voltarem a divergir.

---

## DIV-004 · Agente de vendas "gera propostas", proposta não entra no pipeline

**Aberto** · descoberto na revisão do D-017 (03/08/2026)

**Promessa** — `agent_hub.py:435`:

> "Qualifica leads, precifica serviços e **gera propostas comerciais**"

**Implementação:** `agent_hub.py` tem **zero** referências a `Opportunity`. O
único caminho que cria oportunidade é a rota manual `crm_routes.py:260`
(`CRMService.create_opportunity`).

Gerar a proposta e registrar a oportunidade são dois atos desconectados: quem usa
o agente lança a oportunidade à mão, ou o pipeline não reflete o que foi
proposto.

**Impacto:** comercial — proposta é o que justifica o plano Profissional; se ela
não alimenta o funil, o CRM mostra um pipeline mais vazio que a realidade. E UX —
trabalho duplicado que o usuário não tem como saber que precisa fazer.

**Decisão:** nenhuma. **Registrado, não priorizado** — congelamento D-010 em
vigor, e isto não impede cinco pessoas de usar o produto por uma semana.

**Critério para encerrar:** ou gerar proposta cria/atualiza a oportunidade, ou a
descrição do agente deixa de prometer o que ele não faz. **Uma das duas.**

---

## Encerrados

**Não ficam aqui.** Por regra, item resolvido sai do arquivo e permanece no
histórico que já o comprova:

| O que era | Onde vive agora |
|---|---|
| Exportação LGPD devolvia 200 com seções vazias | **E-047** *(D-018, critério 2 — direito de titular)* · `test_backup_exportacao.py` |
| Motor de notificações nunca chegava ao usuário | `test_notificacoes_vivas.py` + commit — **sem identificador**, por D-018 |

A diferença entre as duas linhas **é o D-018 funcionando**: não é "tudo ganha
ID" nem "nada ganha ID" — é o critério decidindo caso a caso.
