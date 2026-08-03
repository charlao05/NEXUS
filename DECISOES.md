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
