# Divergências — o produto comunica exatamente o que ele faz?

**Registro permanente de desalinhamentos** entre produto, documentação,
arquitetura e implementação.

**Não é lista de bugs.** Bug é comportamento errado. Divergência é
comportamento *possivelmente correto* que **não corresponde ao que foi
prometido** — na página, no plano, na documentação ou no princípio arquitetural.

## Por que existe um documento só para isso

Cada documento do projeto responde uma pergunta diferente:

| Documento | Pergunta |
|---|---|
| `DECISOES.md` | por que uma decisão foi tomada |
| `PORTAO_A.md` | o que bloqueia colocar usuários |
| `PORTAO_O.md` | o que bloqueia operar |
| `ARCH_PRINCIPLES.md` | quais regras a arquitetura promete cumprir |
| `docs/SPIKE_*.md` | o que seria preciso, se um dia |
| **este** | **o produto comunica exatamente o que ele faz?** |

Nenhum dos outros responde esta. E ela vai aparecer muitas vezes, **inclusive
depois do Portão O** — a divergência entre promessa e realidade não é um estado
de lançamento, é um risco permanente de qualquer produto que se comunica.

⚠️ **Não confundir com a futura Matriz de Funcionalidades.** A Matriz responde
*"a funcionalidade existe, em qual plano, em qual módulo?"*. Este documento
responde *"existe diferença entre promessa e realidade?"*. São camadas
diferentes: uma funcionalidade pode existir, estar no plano certo, e ainda assim
ser comunicada de forma que não corresponde ao que ela faz.

## Categorias

| Tipo | Exemplo |
|---|---|
| **Produto × Implementação** | PIX prometido na página, checkout não oferece |
| **Documentação × Código** | README diz X, código faz Y |
| **Arquitetura × Runtime** | princípio diz determinístico, runtime usa LLM |
| **Comercial × Produto** | plano promete recurso inexistente |
| **UX × Backend** | botão existe mas endpoint não |

## Como usar

Cada item tem identificador `DIV-NNN`, evidência em `arquivo:linha`, e **critério
objetivo de encerramento**. Item sem critério de encerramento não entra — vira
observação, e observação não se fecha.

**Item encerrado não é apagado.** O histórico é o valor: mostra que classe de
desalinhamento este produto produz.

---

## DIV-001 · PIX prometido no addon, checkout oferece só cartão

| | |
|---|---|
| **Categoria** | Produto × Implementação |
| **Situação** | 🔴 **Aberto** |
| **Descoberto em** | E-046 (03/08/2026) |
| **Relacionado** | D-017 · `SPIKE_MULTI_GATEWAY.md` |

**Promessa** — `Pricing.tsx:359-366`, no bloco do addon:

> "Precisa de Mais Clientes Sem Mudar de Plano? … R$ 12,90 (compra única)"
> "💳 Cartão ou **PIX** — QR Code válido por 30 min"

**Implementação atual** — `auth.py:1523-1536`:

```python
session = stripe.checkout.Session.create(
    payment_method_types=["card"],     # ← :1524
    ...
    mode="payment",                    # ← :1536
)
```

**Impacto**

- **Comercial:** o cliente lê PIX, clica, e encontra só cartão. Num público de
  MEI, onde Pix é o meio mais familiar, isso custa conversão no exato ponto da
  compra.
- **Jurídico:** é afirmação sobre condição de pagamento numa página de venda.
- **UX:** o detalhe *"QR Code válido por 30 min"* corresponde ao
  `expires_after_seconds` do Pix da Stripe — a copy descreve um fluxo real, que
  não acontece.

**O que torna este item resolvível (e é o ponto principal)**

O addon é `mode="payment"`, **pagamento único** — e Pix avulso **é suportado**
pela Stripe nesse modo, inclusive em conta BR. O que bloqueia é a linha
`payment_method_types=["card"]`, que além de excluir Pix ainda **desliga os
métodos dinâmicos** configurados no painel.

⚠️ **Não confundir com a restrição de assinatura.** Pix em `mode="subscription"`
exige Pix Automático, indisponível para conta Stripe BR nesta data (D-017). Isso
vale para os planos — **não** para este addon. A primeira análise deste item
atribuiu a causa errada; ver a correção de rota em E-046.

**Decisão** — pendente de uma verificação de painel, duas informações:

```
dashboard.stripe.com/settings/account          → Country: ______
dashboard.stripe.com/settings/payment_methods  → Pix: [ativo/inativo/indisponível]
```

| Country | Pix avulso | Ação |
|---|---|---|
| BR | ativo | **cumprir a promessa** — `payment_method_types=["card","pix"]` em `auth.py:1524` |
| BR | inativo/indisponível | **alinhar a copy** — `Pricing.tsx:365` diz só o que entrega |
| ≠ BR | qualquer | reabrir D-017 — Pix Automático estaria disponível |

**Critério para encerrar:** a página de preços e o checkout do addon comunicam o
mesmo conjunto de meios de pagamento, com teste que falhe se voltarem a divergir.

---

## DIV-002 · Exportação LGPD prometia os dados, devolvia vazio

| | |
|---|---|
| **Categoria** | Produto × Implementação |
| **Situação** | ✅ **Encerrado** (02/08/2026) |
| **Relacionado** | direito do titular (LGPD) |

**Promessa:** `GET /api/auth/export-my-data` — exportar os dados do usuário.

**Implementação anterior:** um `except Exception` sem tipo engolia a falha e
devolvia **HTTP 200 com as seções vazias**. A causa era `.get("appointments")`
chamado sobre uma lista. **Nunca funcionou, para nenhum usuário.**

**Impacto:** jurídico — resposta a pedido de titular que parecia bem-sucedida e
não entregava nada. É o pior formato de falha: silenciosa e com aparência de
sucesso.

**Como foi encerrado:** tratamento por seção com log e stack, campos
`secoes_com_falha` e `completa` na resposta — o consumidor passa a saber se a
exportação está íntegra. Coberto por `test_backup_exportacao.py` (5 testes).

**Critério de encerramento (cumprido):** exportação devolve dados reais, e uma
falha parcial é declarada na própria resposta em vez de virar 200 silencioso.

---

## DIV-003 · Motor de notificações existia, nunca chegava ao usuário

| | |
|---|---|
| **Categoria** | Produto × Implementação |
| **Situação** | ✅ **Encerrado** (02/08/2026) |

**Promessa:** o produto tem notificações proativas — cobranças a vencer,
compromissos, limite do MEI.

**Implementação anterior:** o motor de regras existia e funcionava, mas
`/unread` não o consultava. As notificações eram calculadas e **descartadas**.
Havia ainda um travamento com datas *naive* × *aware* que fazia o motor devolver
lista vazia sem erro.

**Impacto:** UX e comercial — funcionalidade construída, paga em esforço, e
invisível para quem usa.

**Como foi encerrado:** `/unread` passou a fundir as regras proativas com IDs
estáveis; a falha de datetime foi corrigida. Coberto por
`test_notificacoes_vivas.py` (6 testes).

⚠️ **A lição deste item:** os primeiros testes passavam **vazios** — a função
devolvia `[]` e o teste concordava. Só um contraprova revelou. *Teste de
ausência sem contraprova é satisfeito por função quebrada.*

---

## DIV-004 · Agente de vendas "gera propostas", proposta não entra no pipeline

| | |
|---|---|
| **Categoria** | Produto × Implementação |
| **Situação** | 🔴 **Aberto** |
| **Descoberto em** | revisão do D-017 (03/08/2026) |

**Promessa** — `agent_hub.py:435`:

> "Qualifica leads, precifica serviços e **gera propostas comerciais**"

**Implementação atual:** `agent_hub.py` tem **zero** referências a
`Opportunity`. O único caminho que cria oportunidade no pipeline é a rota
manual `crm_routes.py:260` (`CRMService.create_opportunity`).

Gerar a proposta e registrar a oportunidade são dois atos desconectados: quem
usa o agente precisa lançar a oportunidade à mão, ou o pipeline simplesmente não
reflete o que foi proposto.

**Impacto**

- **Comercial:** proposta é o que justifica o plano Profissional. Se ela não
  alimenta o funil, o CRM mostra um pipeline mais vazio que a realidade.
- **UX:** trabalho duplicado, e o usuário não tem como saber que precisa fazê-lo.

**Decisão:** nenhuma — item **registrado, não priorizado**. Congelamento D-010
em vigor, e isto não impede cinco pessoas de usar o produto por uma semana.

**Critério para encerrar:** ou gerar proposta cria/atualiza a oportunidade, ou a
descrição do agente deixa de prometer o que ele não faz. **Uma das duas** — a
divergência fecha pelos dois lados.

---

## Como registrar um item novo

```
## DIV-NNN · <título em uma linha>

| Categoria | um dos cinco tipos |
| Situação  | 🔴 Aberto / ✅ Encerrado |
| Descoberto em | E-NNN, ou de onde veio |
| Relacionado | D-NNN, outros DIV |

**Promessa:**            o que o produto comunica — cite a fonte, arquivo:linha
**Implementação atual:** o que o código faz — arquivo:linha
**Impacto:**             comercial · jurídico · UX
**Decisão:**             o que foi decidido, ou "registrado, não priorizado"
**Critério para encerrar:** objetivo e verificável
```

**Regras:**

1. **Toda promessa precisa de fonte citável.** "O produto dá a entender" não é
   promessa — é interpretação.
2. **Todo item precisa de critério de encerramento**, e ele quase sempre tem dois
   lados: *cumprir a promessa* ou *corrigir a comunicação*. Escolher é decisão de
   produto, não de engenharia.
3. **Encerrado não se apaga.**
