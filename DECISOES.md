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
