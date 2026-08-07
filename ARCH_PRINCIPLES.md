# Princípios Arquiteturais do NEXUS

**Este documento é usado em code review.** Quando alguém propõe um atalho, a
conversa não é sobre gosto — é sobre qual princípio está sendo violado, e com
que justificativa.

> **Um princípio sem mecanismo é cartaz na parede.** Cada regra abaixo diz o que
> a garante. As que ainda não têm mecanismo estão marcadas 🟡 — e isso é
> informação, não vergonha: é a lista do que falta construir.

---

# O meta-princípio

**Não é o 11º princípio** — é a propriedade que os dez compartilham, e o teste
que um princípio novo precisa passar para entrar aqui.

> **Todo artefato _governado_ declara por que existe.**
> **Todo artefato governado e _contingente_ declara também quando deixa de existir.**

**Governado** — rascunho, notebook descartável e saída de análise não devem nada
a ninguém. A fronteira está no **D-018**, e não é repetida aqui de propósito.

**Contingente** = exceção · dívida · estrutura transitória · decisão revisável ·
procedimento. Invariante declara só a primeira metade: **exigir prazo de um
invariante é contradição.**

*Verificado (03/08/2026): os dez declaram por quê; quatro declaram também quando
acabam — #2 `expires`, #3 D-012, #4 e #5 pelo 🟡, #9 D-016. Os outros seis são
invariantes.*

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

### Corolário — enquanto a dívida existir (D-012)

> Sempre que uma resposta envolver obrigação tributária, cálculo de imposto,
> multa, juros ou prazo legal, o sistema deve informar claramente **quando o
> resultado é estimado** e quando foi calculado por regra determinística.

Não exige refatoração — muda como a resposta se apresenta:

```
❌  "A multa ficou em R$ 47,32."
✅  "Estimativa: cerca de R$ 47,32. Os juros dependem da Selic acumulada —
     confirme no Portal do Simples Nacional antes de emitir a guia."
```

**Mecanismo:** ✅ instrução no prompt fiscal · `test_fiscal_estimativa.py` (6)

O que sustenta isso como limitação aceitável, e não como bloqueio: **o NEXUS
orienta, não executa ato fiscal.** Não emite DAS, não gera DARF, não declara,
não envia nada a órgão público. No dia em que executar, estas ações migram para
determinístico — o erro deixa de ser informação imprecisa e passa a ter
consequência financeira.

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

## 7. O efeito, não o código de retorno

**Nunca considerar sucesso porque o HTTP devolveu 200, o CI ficou verde ou o
healthcheck respondeu OK. Sempre procurar o efeito esperado.**

| Em vez de | Pergunte |
|---|---|
| "o webhook respondeu 200" | **o plano do usuário mudou?** |
| "o cadastro retornou 201" | **ele consegue entrar?** |
| "a exportação respondeu 200" | **o arquivo tem dados dentro?** |
| "a notificação foi criada" | **apareceu para o usuário?** |
| "o CI está verde" | **o teste exercita esse caminho?** |
| "o `/health` diz ok" | **ok em relação a quê?** |

**Mecanismo:** ✅ prática obrigatória em teste e em runbook — todo passo do
[`PORTAO_O.md`](PORTAO_O.md) termina em teste de efeito, nunca em "configurei"

**Por que virou princípio: aconteceu quatro vezes nesta auditoria, sempre com a
mesma forma.**

| Caso | O sinal dizia | A realidade era |
|---|---|---|
| Webhook do Stripe | **200** | `{"status": "error"}` — o cliente pagava e não recebia acesso. `_stripe_webhook_handler.py:602` devolve 200 **mesmo quando falha**, de propósito, para o Stripe não reenviar |
| CI | **verde**, 4 jobs | aprovou um commit que quebrou o pagamento — o caminho não tinha teste |
| `/health` | **ok** | subia sem `RESEND_API_KEY`: recuperação de senha morta, healthcheck aprovando |
| Exportação LGPD | **200** | todas as seções vazias — o usuário levava um arquivo que parecia backup |

Nos quatro, o sinal era tecnicamente correto e **respondia a pergunta errada**.

**O corolário para teste:** asserção sobre status é o piso, não o teto. Um teste
que só checa `status_code == 200` teria passado em todos os quatro casos acima.

---

## 8. Prova por mutação, não por "verde"

Teste que passa não prova nada até se mostrar que ele **quebra**.

**Mecanismo:** ✅ prática obrigatória em todo mecanismo de proteção

Remove-se o filtro de propósito, confirma-se que o teste acusa **o sintoma
certo**, restaura-se, confere-se `git diff` limpo.

**Por que virou regra:** um teste de isolamento sem contraprova é satisfeito por
uma função quebrada — *"ninguém vê nada"* passa em todo assert de isolamento.
Foi assim que se descobriu que o motor de notificações estava mudo: o teste de
vazamento passava porque a função devolvia lista vazia.

---

## 9. Risco operacional tem o mesmo peso que bug de código

Configuração de painel derruba produto igual a código errado — e é **mais
traiçoeira**, porque não passa por revisão, não tem teste e não deixa rastro no
`git log`.

**Mecanismo:** ✅ [`PORTAO_O.md`](PORTAO_O.md) — todo procedimento tem
`COMO VERIFICAR` **e** `COMO DESFAZER`

**O caso que fundou o princípio:** `render.yaml:28-31` aponta `DATABASE_URL`
para o Postgres do Render, mas produção usa Neon — o valor real existe só no
painel. Reaplicar o blueprint troca o banco por um **vazio**, e o sistema **não
cai**: `/health` responde `database: connected`, a aplicação sobe, e os dados
somem de vista.

Nenhum teste pega isso. Nenhum code review pega isso.

**As duas regras que saem daí:**
- **D-014** — nunca reaplicar blueprint sem validar as variáveis críticas antes
- **D-016** — todo procedimento crítico tem rollback documentado: *"fazer, e
  voltar atrás"*

---

## 10. Nenhuma evidência estrutural substitui a observação do fluxo real de execução

Quando a conclusão depende do **comportamento** do sistema, ler o código não
basta — em nenhum nível de sofisticação. Irmão do **#7** (*não confie no sinal*)
e do **#8** (*não confie no verde*).

| Camada | Entrega | Não vê |
|---|---|---|
| **1 · busca textual** | a linha | o bloco; se o nome é o referente |
| **2 · estrutura estática** | grafo de chamadas, árvore de rotas | despacho dinâmico, colisão de registro |
| **3 · fluxo de execução** | o que **acontece** | — |

**A camada é definida pela afirmação — e é piso, não teto.** Texto e forma → 1.
Estrutura (*"a rota está registrada", "A chama B"*) → 2. **Comportamento**
(*"vaza", "protege", "o usuário recebe"*) → **3**.

> **É permitido subir uma camada para reduzir incerteza relevante. O que não é
> permitido é concluir usando uma camada insuficiente.**

São grandezas diferentes: a **afirmação** define o piso; a **decisão** define se
vale subir acima dele. *"Esta consulta faz N+1"* é estrutural — mas subir à 3
pode mostrar 3 ms por cache, e a camada 2 bastava para a afirmação **e não para a
decisão de reportá-la**.

O escape é unilateral porque os erros não custam o mesmo: **subir sem precisar
custa tempo (recuperável); concluir abaixo do mínimo custa correção pública (não
recuperável)**.

🔴 **Subida obrigatória:** despacho dinâmico, herança, decorator, middleware ou
colisão de registro — a camada 2 não conclui.

**Sete casos desta auditoria** — *o que decidia, e estava fora da evidência
usada:*

1. `/api/crm/dashboard` — `crm_routes.py:396` sempre isolou; o defeito era de outra rota
2. `precos_coerentes` — era a função (`config_check.py:408`); o campo é `precos_ok` (`:545`) · E-045
3. `Pricing.tsx:365` — as 6 linhas acima diziam "compra única": bloco do addon · E-046
4. `billing.py` — `:14` declara `prefix="/api/auth"` e colide com `auth.py:464` · E-040
5. webhooks — `_HANDLERS` (`_stripe_webhook_handler.py:495`) resolve em runtime
6. notificações — asserts verdes sobre função que devolvia `[]` · ver #8
7. exportação LGPD — `except Exception` engolia o desvio · E-047 *(também no #7: dois modos de falha)*

> **"X existe" + "Y tem o defeito" nunca prova "X expõe o defeito".**

⚠️ Nenhum é defeito do código — todos são conclusões maiores que a evidência que
as sustentava, reveladas por **um processo que exige a origem de cada
afirmação**. O princípio existe para que esse processo não dependa de quem
revisa.

**O princípio inteiro cabe numa linha:**

> **Não medir menos do que a afirmação exige, nem mais do que a decisão
> justifica.**

---

## Como usar isto em revisão

1. A mudança viola algum princípio? Qual, e com que justificativa?
2. Se abre exceção: tem `motivo`, `ticket` e `expires`?
3. Se é ponto de entrada novo: entrou no `MAPA_DE_ENTRADAS.md`?
4. Se toca dinheiro, isolamento, autenticação ou a jornada do primeiro cliente:
   **tem teste que falha se quebrar?**
5. Se é proteção: foi provada por mutação?
6. Se o teste checa `status_code`: **checa também o efeito?**
7. Se é procedimento de painel: **tem como desfazer escrito?**
8. Se a conclusão veio de `grep` ou leitura local: **qual código realmente roda?**
9. Se cria família documental nova: respondeu as **três perguntas do D-018** —
   inclusive *"qual evento encerra esta família?"*

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
