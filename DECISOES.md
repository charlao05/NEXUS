# Decisões Arquiteturais — D-001…

**Uma evidência responde *"o que descobrimos?"*. Uma decisão responde *"o que
escolhemos?"*.**

O registro de evidências (`AUDITORIA_NEXUS/16_REGISTRO_EVIDENCIAS.md`, E-001…)
guarda medições. Este guarda escolhas — inclusive as de **não fazer**, que são
as que somem do radar sem um lugar próprio.

Formato: o que foi decidido · por quê (apontando E-xxx) · o que mudou em código.

---

## D-001 · Toda exceção de tenant tem ticket e prazo
**Data:** 01/08/2026

**Motivo:** E-041, E-042. Três vazamentos em três dias, todos com a mesma causa
— o isolamento dependia de alguém lembrar.

**Consequência:** `sem_tenant(motivo, ticket, expires)`. Em produção os três são
obrigatórios (detecção automática pelo arquivo do chamador). Prazo vencido avisa
sempre, falha em dev/CI, **nunca derruba produção**.

**Por que o prazo:** exceção temporária vira permanente e ninguém percebe. Com
data, ela se anuncia sozinha. `PERMANENTE` existe para o que é permanente por
desenho — e obriga a dizer isso conscientemente.

---

## D-002 · Isolamento por tenant é garantia arquitetural, não disciplina
**Data:** 01/08/2026

**Motivo:** E-031, E-041. Corrigir cada query era lavar a mão; faltava a pia.

**Consequência:** `app/core/tenant.py`. 16 modelos marcados **por tipo**
(`TenantScopedModel`), duas camadas — ORM filtra, motor bloqueia o que o ORM não
enxerga (`Query.count()`, SQL cru).

**Modo de falha invertido:** esquecer o filtro passa a significar **ver menos**,
nunca vazar.

---

## D-003 · Proativa é vista do estado, não evento
**Data:** 01/08/2026

**Motivo:** ligar o motor de notificações exigia decidir o que acontece quando o
usuário "dispensa" um aviso.

**Consequência:** notificações proativas não carregam estado de leitura. Somem
quando a condição acaba — fatura paga, compromisso passado. Id derivado do
conteúdo, não do relógio, senão o *dedup* do front falha e a mesma cobrança
reaparece a cada 30 segundos.

**O que isso dispensa:** tabela de dismissals, e a pergunta "por quanto tempo
guardo?".

---

## Adiado — com motivo, para não sumir

### D-004 · `Interaction` e `Opportunity` continuam isolando por join
**Adiado até:** depois do piloto

Não têm `user_id` próprio; isolam por join com `Client`. É a **única** exceção à
regra de isolamento, declarada em `test_pia.py::EXCECOES_DECLARADAS`.

**Por que adiar:** a migration (coluna, backfill, NOT NULL, FK, índice, teste de
consistência) melhora a arquitetura e **não impede cinco pessoas de trabalhar**.
O join funciona hoje.

### D-005 · `Query.count()` continua como está
**Adiado até:** depois do piloto

18 ocorrências em produção. `Query.count()` gera `SELECT count(*) FROM
(subquery)`: o statement externo não tem mapper e a camada 1 do isolamento é
cega para ele.

**Por que não bloqueia:** todas as 18 já filtram por `user_id` explicitamente.
O risco é o **próximo** dev que confie na pia e escreva `.count()`. Converter
para `func.count(M.id)` + lint fica para depois.

### D-006 · Sem tabela `tenant_guard_events`
**Adiado até:** haver volume que justifique

Fica o **log estruturado** dos dois eventos (`sem_tenant` e
`TenantContextMissing`) — com cinco usuários, é o único sinal que diria que algo
começou a vazar, e custa dez linhas.

**Por que não a tabela:** *instrumente o que representa decisão arquitetural, não
tudo o que acontece.* Métrica por endpoint e contagem por tenant só quando
houver uso que justifique.

### D-007 · Sem `MAPA_DE_ENTRADAS.md` gerado
**Adiado até:** depois do piloto

**O que se aprendeu tentando:** duas abordagens estáticas falharam no mesmo
ponto — `_stripe_webhook_handler.py:570` usa despacho dinâmico
(`handler = _HANDLERS.get(...)`), e nenhuma análise de grafo segue essa aresta.
Um Mapa puramente estático teria o ponto cego **exatamente onde está o
dinheiro**.

O Mapa precisaria ser observado em runtime. É bom — e não impede ninguém de
trabalhar.

### D-008 · Nenhuma matriz nasce antes de existir um usuário
**Adiado até:** depois do piloto

**Inverte a sequência anterior**, e a razão é forte: hoje a matriz sairia de
leitura de código; depois do piloto, de comportamento observado. Ela vai mudar —
talvez ninguém use agenda, talvez proposta seja o que vende.

**Consequência:** matriz, módulos, planos e pricing (Portão B) saem da frente.

### D-009 · Central de Prioridades: desenhar, não construir
**Adiado até:** haver mais módulos e comportamento observado

Quanto mais módulos existirem, mais inteligente ela nasce. Hoje conheceria
agenda, financeiro e clientes; depois pode conhecer estoque, metas, cobrança e
uso real.

**O que existe hoje:** as 6 regras determinísticas, ligadas (D-003). **O que não
entra:** ação sugerida, priorização por contexto, IA.

---

## D-011 · O Portão A termina quando o risco deixa de ser estrutural
**Data:** 02/08/2026

**Decisão (texto do dono):** *o Portão A termina quando o risco deixa de ser
estrutural e passa a ser aprendizado de produto.*

**Motivo:** depois desse ponto, o próximo ganho vem de observar usuários, não de
fortalecer a arquitetura. Protege de uma tentação comum — sempre encontrar mais
uma melhoria arquitetural antes de mostrar o produto para alguém.

**Consequência:** o Portão A fechou em 02/08/2026 com 515 testes e 0 falhas.

---

## D-012 · Cálculo fiscal feito por IA se apresenta como estimativa
**Data:** 02/08/2026

**Motivo:** E-036. 10 ações fiscais são respondidas por LLM antes do cálculo
determinístico. O risco **não é uniforme** — e essa distinção é o que permite
não bloquear o piloto:

| Grupo | Exemplo | Risco |
|---|---|---|
| repetir constante | DAS R$ 86,05, limite R$ 81.000 | baixo — ancorado no prompt |
| interpretação | explicar regra, quando emitir nota | moderado, conferível |
| **cálculo** | **multa, juros, IRPF** | 🔴 *"pode parecer extremamente convincente e ainda assim estar errada"* |

**Decisão:** não bloqueia — **mas não pode parecer oficial.** Valor que a IA
calculou se apresenta como **estimativa**, com a fonte oficial para conferir
**antes de pagar ou declarar**.

**Consequência:** instrução no prompt fiscal (`agent_chat.py`). O bloco deixou
de se anunciar como `MULTAS (informação real)` — a **regra** é oficial, o
**valor calculado a partir dela** não é. Não exigiu refatoração: mudou como a
resposta se apresenta. Travado por `test_fiscal_estimativa.py` (6 testes),
incluindo um que quebra se as constantes do prompt divergirem das do código.

**Gatilho que reabre:** o dia em que o NEXUS emitir DAS, gerar DARF, calcular
imposto automaticamente, preencher declaração ou enviar informação a órgão
público. Aí o erro deixa de ser informação imprecisa e passa a ter consequência
financeira — e as 10 ações migram para determinístico.

---

## D-013 · Portão A (engenharia) é separado de Portão O (operação)
**Data:** 02/08/2026

**Motivo:** o Portão A estava dependendo de Render pago e PITR do Neon. Um
portão de engenharia que não fecha porque uma fatura não foi paga **deixa de
medir engenharia**.

**Decisão:**

| | Prova | Resultado |
|---|---|---|
| **Portão A** | repositório | PASSOU / NÃO PASSOU |
| **Portão O** | painel de provedor | PRONTO PARA PRODUÇÃO / AINDA NÃO |

**A confirmação de que o corte é real:** dos 515 testes, os **dois únicos
`SKIPPED`** são `STRIPE_WEBHOOK_SECRET ausente` e `pacote 'resend' nao
instalado` — ambos Portão O. A suíte de engenharia só não consegue verificar
aquilo que não é engenharia.

**Evita o modo de falha:** a equipe dizer *"não passou no Portão A"* quando o
que falta é pagar uma conta do provedor.

---

## D-014 · Nunca reaplicar blueprint sem validar as variáveis críticas antes
**Data:** 02/08/2026

**Motivo:** `render.yaml:28-31` aponta `DATABASE_URL` para o `nexus-db`
(Postgres do Render), mas produção usa **Neon** — o valor real existe só no
painel. Reaplicar o blueprint troca o banco por um **vazio**.

**E o sistema não cai.** `/health` responde `database: connected`, a aplicação
sobe normal, e os dados somem de vista. É o pior formato de falha: parece que
está tudo bem.

**Consequência:** checklist obrigatório no topo do `PORTAO_O.md` — copiar todos
os valores atuais **antes** de tocar em qualquer coisa, e trabalhar só pela aba
Environment. Nunca `Sync` / `Reapply blueprint` em produção.

---

## D-015 · As 4 variáveis do Stripe live vão num único Save
**Data:** 02/08/2026

**Motivo:** o Stripe recusa chave live com price de teste (e o contrário).
Salvar em duas etapas deixa o sistema **quebrado no intervalo** — e cada Save
dispara um redeploy de 2 a 5 minutos, então o intervalo é real.

**Consequência:** procedimento oficial, na ida **e na volta**:
`STRIPE_SECRET_KEY` + os 3 `STRIPE_PRICE_*` sempre juntos.

**Verificação:** `/health` → `stripe.precos_ok` confere se cada price existe
**no mesmo modo da chave**. Meio rollback deixa esse campo `false` — pior que
qualquer um dos dois estados inteiros.

⚠️ **O campo é `precos_ok` (`config_check.py:545`);
`stripe_precos_coerentes()` é a função que o calcula (`config_check.py:408`).**
Nome de função vazou para a documentação e mandaria o executor procurar no
`/health` um campo que não existe. Corrigido em 03/08/2026 no passe adversarial
dos runbooks.

---

## D-016 · Todo procedimento crítico tem rollback documentado
**Data:** 02/08/2026

**Decisão (do dono):** *"Todo procedimento crítico deveria ter: fazer; e voltar
atrás."*

**Motivo:** o runbook mandava alterar cinco coisas em produção e não dizia como
voltar de nenhuma.

**Consequência:** cada bloqueador do `PORTAO_O.md` ganhou `COMO DESFAZER` com
cinco campos — qual variável restaurar · onde achar o valor antigo · como
confirmar que voltou · quanto esperar · como validar.

**E o que o rollback revelou** — três coisas que só apareceram ao escrever o
caminho de volta:

- **`Delete` no Render não tem volta.** Por isso o procedimento manda
  `Suspend` primeiro.
- **Depois da primeira venda, voltar o Stripe para teste deixa de ser
  rollback** — a cobrança continua existindo e o NEXUS deixa de enxergá-la.
- **Restaurar por PITR descarta tudo que veio depois do ponto escolhido.**
  Restaurar para um branch novo do Neon, comparar, e só então promover.

---

## D-010 · Congelar a fundação quando o Portão A fechar
**Data:** 02/08/2026

**Motivo:** *"existe um momento em que a arquitetura deixa de reduzir risco e
começa a atrasar aprendizado."*

**Consequência:** fechado o Portão A, nada de fundação nova até o piloto
responder o que nenhuma auditoria responde — alguém paga? usa todo dia? indica?
abandona?

**O filtro que decide o que entra:** *o que ainda impede cinco pessoas reais de
usar isso durante uma semana?* — e não *o que ainda pode ser melhorado?*. A
segunda pergunta nunca acaba.

🔴 **O filtro vale também para método e documentação** *(acrescentado em
07/08/2026)*. O método passou por baixo deste congelamento porque *"é só
documentação"* — e produziu **quatro entregas seguidas, 432 linhas, zero de
produto**. Melhoria de método não impede ninguém de usar o produto: enquanto o
Portão O estiver aberto, ela reprova na primeira pergunta do filtro do D-018.

---

## D-017 · O gateway continua Stripe — nesta escala
**Data:** 03/08/2026

Chegou um relatório de pesquisa recomendando, na prática, migrar para o Mercado
Pago. A pesquisa foi avaliada contra a fonte, não contra a impressão. O desenho
arquitetural dela é bom e foi preservado em
[`docs/SPIKE_MULTI_GATEWAY.md`](docs/SPIKE_MULTI_GATEWAY.md); a recomendação não
se sustentou.

**Decisão:** o gateway permanece **Stripe**. Nenhuma migração, nenhuma camada de
abstração, nenhuma refatoração nesta fase.

> ## 📌 O achado que dimensiona o projeto
>
> **Não é o Pix. É o schema.**
>
> ```
> User.stripe_customer_id              models.py:253    unique
> Subscription.stripe_subscription_id  models.py:349    unique
> InvoicePayment.stripe_invoice_id     models.py:1102   unique
> ```
>
> **Uma coluna única chamada `stripe_*` não comporta o ID de outro provedor.**
>
> Trocar de gateway **não é trocar de SDK** — é migrar o modelo de dados para
> pares `(provider, external_id)`, com unicidade composta, em tabelas que
> guardam o histórico financeiro. Mudança de schema, com dados de produção
> dentro. Isso, e não a API do gateway, é o que define o tamanho do projeto.
>
> O segundo maior custo também não é código: é a **reautorização de meio de
> pagamento** de cada cliente pagante. Ver `docs/SPIKE_MULTI_GATEWAY.md` §3 e §5.1.

Este registro separa **fato**, **medição** e **premissa** de propósito. Misturar
os três é como uma decisão vira dogma: daqui a seis meses alguém lê a conclusão
sem o contexto que a produziu.

### Fatos verificados (03/08/2026)

| Fato | Onde |
|---|---|
| Na data desta decisão, **Pix Automático não está disponível para contas Stripe no Brasil** | docs.stripe.com/payments/pix |
| Pix Automático **existe e está em produção** na Stripe — mandates, pré-débito de 3 dias, retries, Billing | docs.stripe.com/payments/pix/pix-automatico |
| Os **dois** checkouts vivos aceitam somente cartão | `auth.py:1340` (assinatura) e `auth.py:1524` (addon) — `payment_method_types=["card"]` |
| A página de preços **promete PIX** — no bloco do **addon** | `Pricing.tsx:359-366` |
| Pix em `mode="subscription"` exige Pix Automático | docs da Stripe, seção Checkout |
| O addon é `mode="payment"` — onde **Pix avulso é suportado** | `auth.py:1536` |
| Acoplamento medido: **457 linhas**, 12 arquivos-fonte + 10 de teste | `grep -rin stripe` |
| As colunas de provedor são `unique=True` | `models.py:253`, `:349`, `:1102` |
| Duas gerações de preço **ativas no mesmo produto** | API viva — `prod_UB7yU4HCQnB7Yk` tem 29,90 **e** 39,90 |

**A divergência de PIX — e as duas causas distintas.** *Na implementação atual do
NEXUS, a promessa de pagamento por PIX no addon não é atendida.*

| Caminho | Modo | Promete PIX? | Entrega? | Causa |
|---|---|---|---|---|
| Assinatura `auth.py:1339` | `subscription` | não | não | **restrição do provedor** na data — Pix Automático indisponível p/ conta BR |
| Addon R$ 12,90 `auth.py:1523` | `payment` | **sim** (`Pricing.tsx:365`) | não | **escolha de implementação** — `payment_method_types=["card"]` + elegibilidade da conta não verificada |

⚠️ **Correção de rota (registrada, não silenciosa).** A primeira redação deste
registro dizia que a promessa era *"incumprível"* porque assinatura exige Pix
Automático. **Estava errado — e não só forte demais.** O texto de PIX está no
bloco do **addon** (`Pricing.tsx:359-366`), que é `mode="payment"`. Pix avulso
**é suportado** pela Stripe nesse modo. A análise de Pix Automático continua
correta *sobre assinaturas* e **não explica esta promessa**. Ver **E-046**.

Consequência prática: se Pix avulso estiver habilitado na conta, o correto é
**cumprir a promessa**, não apagá-la. Rastreado em
[`docs/DIVERGENCIAS.md`](docs/DIVERGENCIAS.md) → **DIV-001**.

Tudo verificado na rota que **realmente roda** (`authService.ts:274` →
`/api/auth/checkout` → `auth.py:1242`), e não na homônima sombreada de
`billing.py:90` (E-040).

### Medições (dependem de premissas atuais)

> **Os cálculos utilizam as taxas consideradas na pesquisa e representam um
> cenário de simulação.**

Taxas conforme citadas no relatório — **não conferi as tabelas oficiais**.
Depende de MDR, prazo de recebimento, ticket médio e número de clientes.

| Plano | Stripe (3,99% + R$0,39) | MP na hora (4,98%) | MP 30 dias (3,98%) |
|---|---|---|---|
| R$ 29,90 | R$ 1,58 · 5,29% | R$ 1,49 | R$ 1,19 |
| R$ 59,90 | R$ 2,78 · 4,64% | R$ 2,98 | R$ 2,38 |
| R$ 89,90 | R$ 3,98 · 4,42% | R$ 4,48 | R$ 3,58 |

**Ponto de virada: R$ 39,39.** Acima disso a Stripe é mais barata que o Mercado
Pago "na hora". **No cenário analisado, o Mercado Pago apresenta vantagem
econômica apenas quando considerada a liquidação em 30 dias** — o que é o oposto
do que convém a quem já teve serviço suspenso por inadimplência.

O relatório constrói a vantagem do MP sobre **Pix** (0–0,99% vs 1,19%) enquanto
registra que a vertical SaaS é **~79% cartão** e ~13% Pix. A vantagem se aplica à
minoria das transações.

### Premissas — todas podem mudar

| Premissa | Pode mudar? |
|---|---|
| zero clientes pagantes | **sim** |
| Stripe atende os requisitos atuais | **sim** |
| Pix Automático indisponível em conta BR | **sim** |
| custo de migração alto | **sim** |
| acoplamento atual elevado | **sim** |
| produto em fase de validação | **sim** |
| taxas praticadas por Stripe e Mercado Pago | **sim** |

### Conclusão

> **Na escala atual do produto, os benefícios não justificam a troca.** Até o
> momento, não há evidências suficientes de que os benefícios superem o custo e o
> risco da migração.

Não *"o benefício não existe"* — essa formulação é forte demais e envelhece mal.

### Matriz de decisão

| Critério | Situação atual | Impacto |
|---|---|---|
| Produto funciona com Stripe | sim | manter |
| Usuários pagantes | 0 | manter |
| **Pix avulso no addon** | **prometido na página, não oferecido no checkout** | **DIV-001 — verificar a conta e alinhar** |
| Pix em assinatura | exige Pix Automático, indisponível na Stripe BR *(nesta data)* | acompanhar |
| Churn medido | inexistente | insuficiente |
| Custo de migração | alto | manter |
| Ganho financeiro imediato | baixo | manter |
| Acoplamento atual | elevado | não migrar |

### Por que NÃO implementar agora

- **Produção não tem clientes.** Taxa sobre R$ 0 é R$ 0. No piloto de cinco
  usuários a diferença é de cerca de **R$ 2 por mês**.
- **A Stripe atende os requisitos atuais** — cartão recorrente, o meio que
  responde por ~79% da vertical.
- **O custo de migração supera o benefício hoje** — e recai sobre o único
  subsistema que quebrou produção duas vezes esta semana (E-042, E-043).
- **A necessidade do produto ainda não existe.** ⚠️ *Correção de rota:* a
  formulação inicial era *"Pix Automático ainda depende de maturidade do
  ecossistema"*. **Não é o caso** — na Stripe ele está maduro e em produção; o
  que existe é restrição por país da conta. O que ainda não amadureceu é a
  necessidade do produto, não a tecnologia. Registrar a razão imprecisa seria o
  defeito do E-045.
- **A prioridade é validar usuários reais**, não substituir infraestrutura
  financeira (D-010).

### O que NÃO foi avaliado

**Silêncio aqui não é aprovação.** Fora do escopo desta decisão: disponibilidade
e SLA do Mercado Pago · histórico de indisponibilidade · qualidade do suporte ·
estabilidade da API · risco regulatório · estratégia internacional · múltiplas
moedas · evolução do Open Finance · custos operacionais de conciliação.

### Gatilhos de reabertura

> Esta decisão será reavaliada quando houver evidências objetivas de que o
> gateway atual limita o crescimento do negócio. Os gatilhos são: (1) aumento
> sustentado do churn involuntário por falhas de cobrança; (2) demanda recorrente
> e documentada por Pix recorrente/Pix Automático; (3) mudança estratégica do
> produto que exija uma arquitetura de pagamentos mais abrangente (marketplace,
> split, múltiplos gateways ou expansão internacional); ou (4) mudança relevante
> nas capacidades ou condições comerciais dos provedores, suficiente para alterar
> as premissas desta decisão. Até que um desses gatilhos ocorra, a prioridade
> permanece validar o produto com usuários reais, e não substituir a
> infraestrutura de pagamentos.

**Limiar do gatilho (1):** cobranças recusadas acima de **10% por dois meses
consecutivos**.
**Condição do gatilho (2):** só conta **registrado no CRM** — enquanto for
percepção, não é evidência.

**Volume de clientes NÃO é gatilho.** É fácil de medir e mede a coisa errada:
500 clientes satisfeitos no cartão não indicam problema algum, e 50 vendas
perdidas por falta de Pix recorrente indicam — e não aparecem na contagem.

### Resumo

```
STATUS DA DECISÃO

  ✓ Não migrar de gateway

MOTIVOS PRINCIPAIS

  ✓ Produto ainda em validação
  ✓ Custo elevado de migração — e o custo é o SCHEMA, não a API
  ✓ Ganho financeiro baixo na escala atual
  ✓ Pix Automático indisponível para conta Stripe BR (nesta data)

REAVALIAR QUANDO

  ✓ churn involuntário aumentar          (>10% por 2 meses)
  ✓ demanda real por Pix recorrente      (registrada no CRM)
  ✓ mudança estratégica do produto       (marketplace, split, internacional)
  ✓ mudança relevante nas capacidades dos provedores

EM ABERTO, INDEPENDENTE DESTA DECISÃO

  → DIV-001 — PIX prometido no addon e não oferecido no checkout
```

---

## D-018 · Critério para identificadores permanentes
**Data:** 03/08/2026 · **Enxugado em 07/08/2026** — reprovava no próprio critério
(tinha 112 linhas)

**Motivo:** cada descoberta desta auditoria virava estrutura documental nova.
Sem critério, o conhecimento cresce até ficar mais caro navegar que consultar.

### O teste

> **Se este documento nunca existisse, qual decisão concreta seria pior daqui a
> um ano?**

**Se a resposta não for objetiva, o documento não existe.** Esta pergunta absorve
"qual o objetivo", "quem consulta" e "quando vale criar" — todas são
aproximações dela.

### A regra do identificador

Recebe identificador permanente o que **altera decisões futuras** de arquitetura,
produto, operação ou negócio, **ou** cuja **rastreabilidade seja exigida** por
obrigação legal, regulatória, contratual ou de auditoria.

O resto — descoberta pontual, bug corrigido, investigação concluída — fica
vinculado ao registro que motivou (teste, commit, decisão, evidência).

⚖️ O segundo critério já vale: o NEXUS registra consentimento LGPD com IP e
timestamp (`models.py:270-273`) e opera sob prestação de contas. Ali a
granularidade é requisito, não excesso — e foi o que produziu o **E-047**.

### Os dois campos que o teste não responde

| Campo | Pergunta |
|---|---|
| **Duplicação** | que documento responde isso hoje? *(se algum responde, não crie)* |
| **Critério de encerramento** | que evento faz este documento deixar de existir? |

Documento transitório cujo conteúdo passe a ser exigido externamente **deixa de
ser transitório** — o encerramento não vence a obrigação.

### Filtro de melhoria metodológica

Antes de virar documentação permanente: **muda decisões futuras? · resolve erro
recorrente? · cabe em menos de meia página?**

**Qualquer "não" ⇒ não vira documento.**

🔴 **Aplica-se a documento permanente e família nova.** Não a rascunho, anotação
ou saída de análise — exigir isso de uma nota de duas linhas transforma a regra
contra burocracia **em** burocracia.
