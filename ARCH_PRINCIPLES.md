# Princípios Arquiteturais do NEXUS

**Este documento é usado em code review.** Quando alguém propõe um atalho, a
conversa não é sobre gosto — é sobre qual princípio está sendo violado, e com
que justificativa.

> **Um princípio sem mecanismo é cartaz na parede.** Cada regra abaixo diz o que
> a garante. As que ainda não têm mecanismo estão marcadas 🟡 — e isso é
> informação, não vergonha: é a lista do que falta construir.

---

## 1. Falhar fechado é melhor que vazar

Quando falta contexto, informação ou configuração, o sistema **mostra menos** —
nunca mais. Erro de programação deve resultar em "não vi nada", jamais em "vi
o de outro cliente".

**Mecanismo:** ✅ a pia — [`backend/app/core/tenant.py`](backend/app/core/tenant.py)

Toda tabela de negócio herda `TenantScopedModel` e é filtrada automaticamente
pelo tenant corrente. Duas camadas: o ORM **filtra**, o motor **bloqueia** o que
o ORM não enxerga (`Query.count()`, SQL cru). Sem contexto, nada que toque
tabela de tenant passa.

```python
db.query(Invoice).filter(status="pending").all()   # já vem filtrado
```

**Prova:** `backend/tests/test_pia.py` — queries **sem nenhum** `.filter(user_id)`.
Se o isolamento aparece ali, foi a arquitetura. 6 mutações, 6 detecções.

**Por que existe:** três vazamentos em três dias (`analytics_dashboard`,
`notifications`, `agent_media`), todos com a mesma causa — o isolamento dependia
de alguém lembrar. Isso não é um bug; é um mecanismo que produz bugs.

---

## 2. Toda exceção é explícita, rastreável e tem prazo

Acesso global existe e é legítimo (painel do dono, webhook, script). Mas é
**exceção declarada**, nunca padrão silencioso.

**Mecanismo:** ✅ `sem_tenant(motivo, ticket, expires)`

```python
with sem_tenant(
    "webhook Stripe: evento de sistema, sem usuário autenticado",
    ticket="E-042",
    expires=PERMANENTE,      # ou "2027-03-01"
):
    ...
```

- `motivo` **obrigatório** — se não dá para explicar por que este código vê
  todos os tenants, provavelmente ele não deveria ver
- `ticket` e `expires` **obrigatórios em produção** (detectado automaticamente
  pelo arquivo do chamador; fixture de teste é isenta)
- prazo vencido → aviso em log **sempre**, falha em dev/CI, **nunca derruba
  produção** — data que passou não pode virar indisponibilidade para o usuário
- **restrita:** rota de usuário comum não consegue pedir visão global

**A regra em uma frase:**

> Nenhum dado pertence ao sistema. Todo dado pertence a um tenant.
> O acesso global é uma exceção explicitamente declarada e auditável.

**Prova:** `test_escotilhas_de_producao_estao_declaradas` quebra se alguém
acrescentar escotilha sem ticket e prazo.

---

## 3. Determinismo antes de geração

Cálculo é cálculo. IA explica o resultado; **não o produz**.

| | |
|---|---|
| ✅ **Aceito** | `DAS = R$ 86,05` vem do código. A IA diz *"quer que eu explique por quê?"* |
| ❌ **Recusado** | o LLM produzir o valor, a data de vencimento ou a multa |

Vale para: DAS, INSS, IRPF, Simples, juros, multa, faturamento, limite MEI,
orçamento, lead score, fluxo de caixa, margem.

**Mecanismo:** 🟡 **especificado, não garantido** —
`AUDITORIA_NEXUS/21B_ESPECIFICACOES.md`

Hoje **10 ações fiscais são respondidas por LLM** antes de chegar ao código
determinístico (`agent_hub.py:986` intercepta `ACTION_PROMPTS`). O
comportamento correto está especificado; o teste se escreve quando a
implementação mudar.

⚠️ **É a maior dívida arquitetural aberta.** O diferencial do NEXUS existe no
código e está contornado em runtime.

---

## 4. IA só onde ela é indispensável

O mercado põe IA em tudo. Aqui a pergunta é o inverso: **existe algoritmo
tradicional que resolva?** Se existe, IA é luxo — custo variável sem ganho.

| Natureza | O que é | Custo |
|---|---|---|
| **Matemática** | regra fixa (DAS, orçamento, margem) | R$ 0,00 |
| **Dados** | CRUD e consulta | banco |
| **IA** | geração/interpretação sem algoritmo (proposta, transcrição, visão) | por uso |
| **Mista** | cálculo + IA que só explica | IA opcional |
| **Integração externa** | depende de terceiro | disponibilidade alheia |

**Mecanismo:** 🟡 **coluna da Matriz de Funcionalidades — Portão B**

Medido: **15 das 32 ações interceptadas são listagem pura** e passam por IA
**só por herança arquitetural**. Cortar não perde funcionalidade nenhuma — e
`list_clients` já foi convertido (`agent_hub.py:992`), provando o padrão.

---

## 5. Nenhuma decisão de preço sem custo medido

Plano, limite, franquia e degustação saem de **custo medido por funcionalidade**
— nunca de intuição.

**Mecanismo:** 🟡 **parcial**

- ✅ atribuição de consumo por `user_id` e por módulo (`367fbb8`)
- ✅ custo unitário medido (`AUDITORIA_NEXUS/05_MODELAGEM_FINANCEIRA.md`)
- 🟡 Matriz de Funcionalidades — Portão B

**Dispersão medida: 615×** entre uma proposta (R$ 0,003) e uma hora de áudio
(R$ 1,83). Cota única é indefensável.

**Corolário:** não se vende IA. Vende-se tempo. O cliente nunca compra GPT.

---

## 6. Nada em produção sem caminho de teste correspondente

Toda funcionalidade que possa comprometer **dinheiro, isolamento entre
usuários, autenticação ou a jornada do primeiro cliente** precisa de teste que
falhe se ela quebrar.

**Mecanismo:** ✅ Portão A + `MAPA_DE_ENTRADAS.md`

Nenhum webhook, worker ou cron novo entra sem linha no Mapa respondendo:
**"como obtém o tenant?"** e **"o que acontece se não tiver?"**

**A evidência de que isto não é burocracia** — medido em 01/08/2026, nos 12
passos do primeiro cliente:

| | |
|---|---|
| Dos **4 passos sem teste** | **2 estavam quebrados** |
| Dos **8 passos com teste** | **0** |

O pagamento estava quebrado e 4 jobs de CI aprovaram, porque o webhook não
tinha teste. E `billing.py` devolvia 500 em todas as rotas vivas — desde antes,
sem ninguém saber.

> Você não precisa de 144 rotas testadas. Precisa que **100% do risco** esteja
> testado. São coisas diferentes.

---

## 7. Prova por mutação, não por "verde"

Teste que passa não prova nada até se mostrar que ele **quebra**.

**Mecanismo:** ✅ prática obrigatória em todo mecanismo de proteção

Remove-se o filtro de propósito, confirma-se que o teste acusa **o sintoma
certo**, restaura-se, confere-se `git diff` limpo.

**Por que virou regra:** um teste de isolamento sem contraprova é satisfeito por
uma função quebrada — *"ninguém vê nada"* passa em todo assert de isolamento.
Foi assim que se descobriu que o motor de notificações estava mudo: o teste de
vazamento passava porque a função devolvia lista vazia.

---

## Como usar isto em revisão

1. A mudança viola algum princípio? Qual, e com que justificativa?
2. Se abre exceção: tem `motivo`, `ticket` e `expires`?
3. Se é ponto de entrada novo: entrou no `MAPA_DE_ENTRADAS.md`?
4. Se toca dinheiro, isolamento, autenticação ou a jornada do primeiro cliente:
   **tem teste que falha se quebrar?**
5. Se é proteção: foi provada por mutação?

---

## Os três portões

| Portão | Pergunta | Libera |
|---|---|---|
| **A — Confiabilidade** | *posso entregar a cinco pessoas sem risco de perderem dados, dinheiro ou confiança?* | os 5 primeiros usuários |
| **B — Modelo de negócio** | *posso cobrar com transparência?* | cobrar |
| **C — Validação** | *cinco pessoas realmente usaram?* | mexer em plano e preço |

**Quando o A fecha, os usuários entram — sem esperar o B.** A partir dali a
pergunta deixa de ser técnica e vira *"você entendeu?"*, que só um humano
responde.

⚠️ **O Portão A não é avaliação de qualidade.** É checklist: passa ou não passa.
UX, dashboards e automações "nice to have" **nunca** entram como condição dele —
senão vira o ciclo infinito de melhorias que impede o produto de encontrar
usuários reais.
