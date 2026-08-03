# Runbook A — Diagnóstico

# 🔵 SOMENTE LEITURA

**Nenhum passo deste documento altera coisa alguma.** Não paga, não cancela,
não deleta, não edita variável, não cria endpoint.

Se você se pegar clicando em `Save`, `Pay`, `Delete`, `Suspend` ou
`Add endpoint` — **está no documento errado.** Isso é
[`RUNBOOK_B_EXECUCAO.md`](RUNBOOK_B_EXECUCAO.md), e ele só roda depois do
[`CHECKPOINT.md`](CHECKPOINT.md) assinado.

**Objetivo:** produzir as respostas que o checkpoint exige. Sem elas, ninguém
tem como autorizar mudança em produção.

**Valores citados aqui:** [`PARAMETROS.md`](PARAMETROS.md) é a fonte. Se algo
divergir, o `PARAMETROS` vence.

---

## Formato de evidência — use em TODOS os passos

```
EVIDÊNCIA
  Origem:         <URL ou tela exata>
  Resultado:      <o que apareceu, literal — copie, não resuma>
  Como confirmei: <o que você fez para ter certeza>
```

Se não conseguir executar um passo, escreva:

```
❌ NÃO CONSEGUI: <onde parou e por quê>
```

**Não conseguir é aceitável. Inventar não é.** A diferença entre as duas é o
que torna este documento confiável.

---

# A1 · Salvar os valores atuais — o passo que viabiliza todo rollback

**POR QUE PRIMEIRO:** sem isto, nenhum `COMO DESFAZER` deste conjunto funciona.
Não existe voltar atrás sem o valor de antes.

**ONDE:** `https://dashboard.render.com` → `nexus-backend` → **Environment**

**O QUE FAZER** — copie para um gerenciador de senhas, valor por valor:

```
[ ] DATABASE_URL               ← o mais importante
[ ] STRIPE_SECRET_KEY
[ ] STRIPE_PRICE_ESSENCIAL
[ ] STRIPE_PRICE_PROFISSIONAL
[ ] STRIPE_PRICE_COMPLETO
[ ] STRIPE_WEBHOOK_SECRET
[ ] RESEND_API_KEY
[ ] EMAIL_FROM
```

**REGISTRE no checkpoint** (mascarado — 10 primeiros + 4 últimos + comprimento):

```
DATABASE_URL: postgresql:// … <4 últimos>   (___ caracteres)
```

### 🔴 Confira uma coisa específica no `DATABASE_URL`

Ele **precisa** conter `neon.tech`. Se contiver `render.com` ou
`dpg-`, **pare tudo e reporte** — significa que o blueprint já foi reaplicado
em algum momento e a aplicação está apontando para o banco errado.

```
DATABASE_URL contém "neon.tech"?   [ ] sim   [ ] NÃO → PARE
```

**⚠️ Durante toda a operação:** nunca clique em `Sync`, `Reapply blueprint` ou
`Apply changes`. Trabalhe só pela aba **Environment**.

---

# A2 · O que está sendo cobrado

**POR QUE:** `PARAMETROS.md` registra `PLANO_BACKEND = free` e
`PLANO_DB_RENDER = free`. **Serviço free não gera fatura.** Logo há outra coisa
na conta — e a resposta certa pode ser **remover**, não pagar.

**ONDE:** `https://dashboard.render.com` → **Billing** → **Invoices**

**O QUE FAZER** — abra a fatura em aberto e **leia as linhas**:

```
Valor total: R$ ______

Linhas:
  - _______________________  R$ ______
  - _______________________  R$ ______
```

**Depois, liste TODOS os serviços da conta:**

```
nexus-backend    web       plano: ______   estado: ______
nexus-frontend   static    plano: ______   estado: ______
nexus-db         postgres  plano: ______   estado: ______

Algum outro serviço que não está nesta lista? ______________
```

**Pergunta específica:** o `nexus-db` está marcado como *expired*, vencido ou
pedindo upgrade? **Copie a mensagem exata.**

**INTERPRETAÇÃO** — o que cada achado significa:

| Se a cobrança for de | Provável causa | Decisão |
|---|---|---|
| `nexus-db` | Postgres free do Render expira em 90 dias | ⚠️ **não é o banco de produção** — considere deletar em vez de pagar |
| Serviço que você não reconhece | recurso órfão de outra época | investigar antes de qualquer coisa |
| `nexus-backend` ou `nexus-frontend` | upgrade de plano feito e esquecido | conferir se o upgrade ainda é necessário |

⚠️ **Não decida aqui.** Este runbook produz o diagnóstico; a decisão entre
pagar e remover é do dono, no checkpoint.

---

# A3 · O serviço está de pé?

**ONDE:** `https://api.nexxusapp.com.br/health`

**O QUE FAZER** — abra a URL e **cole a resposta inteira** na evidência.

**COMO LER** (`PARAMETROS.md` → *Campos do `/health` que decidem*):

| Campo | Esperado | Anote o que veio |
|---|---|---|
| `status` | `ok` | ______ |
| `database` | `connected` | ______ |
| `config.status` | `ok` | ______ |
| `config.criticas_faltando` | `[]` | ______ |
| `config.degradadas_faltando` | `[]` | ______ |
| `config.stripe.autentica` | `true` | ______ |
| `config.stripe.motivo` | contém `modo live` | ______ |
| `config.stripe.precos_ok` | `true` | ______ |
| `config.stripe.cobranca_operacional` | `true` | ______ |
| `config.automacao_web.disponivel` | `true` | ______ |

🔴 **É `precos_ok`** — `precos_coerentes` é o nome da função no código, **não
aparece no JSON**. Se você procurar por ele e não achar, é porque ele não
existe, não porque o sistema está quebrado.

⚠️ `automacao_web.disponivel: false` significa chromium ausente. **Está previsto
e não bloqueia** — anote e siga.

**Agora é diagnóstico: nada disto aqui está certo ou errado ainda.** É esperado
que `stripe.motivo` diga `modo test` — é justamente o bloqueador 2, e quem
resolve é o passo B1.

**SE A RESPOSTA FOR `This service has been suspended`** — anote isso e siga.
Os passos A4 e A5 não dependem do Render.

---

# A4 · Backup do banco — o PITR do Neon existe?

**POR QUE ESTE PASSO ESTÁ NO DIAGNÓSTICO:** o checkpoint exige *"backup lógico
disponível"*. Se esta verificação viesse depois da execução, **o checkpoint
nunca poderia ser preenchido** — a autorização dependeria de algo descoberto
depois dela.

**ONDE:** `https://console.neon.tech` → projeto do NEXUS → **Settings**
*(pode estar em Branches ou Storage, depende da versão do painel)*

**O QUE RESPONDER:**

```
O plano inclui PITR (point-in-time recovery)?   [ ] sim   [ ] não
Janela de retenção:  ______ dias
Plano atual do projeto:  ________________
Texto exato que o painel mostra: "________________________________"
```

⚠️ **Se não encontrar, escreva `❌ NÃO CONSEGUI` e diga em quais telas
procurou. NÃO estime o número de dias.** Um número inventado aqui vira uma
decisão de risco tomada com informação falsa.

**O QUE JÁ ESTÁ RESOLVIDO:** a metade do **usuário**.
`GET /api/auth/export-my-data` funciona e tem 5 testes
(`test_backup_exportacao.py`) — está no Portão A. Esta é a metade do **banco**,
e são coisas diferentes: se o Neon cair sem PITR, a exportação não recupera
nada.

---

# A5 · E-mail — o domínio está verificado?

**POR QUE:** um usuário que esquece a senha e não recebe o e-mail **perde a
conta**. Não há outro caminho de volta.

**ONDE:** `https://resend.com` → **Domains**

```
Domínio nexxusapp.com.br:  [ ] Verified   [ ] Pending   [ ] não existe
Se Pending — registros DNS que o Resend pede:
  tipo: ______  nome: ______________  valor: ______________

API Keys — existe chave ativa?  [ ] sim  [ ] não
  nome: ______________   criada em: ______
  (NÃO precisa revelar o valor)
```

**E no Render** → Environment → o valor de `EMAIL_FROM`:

```
EMAIL_FROM = ______________________________
```

🔴 **Se contiver `@gmail.com`, destaque.** O Resend **recusa** gmail como
remetente — o e-mail não sai nem com a chave correta e o domínio verificado.

---

# A6 · Estado atual do Stripe

**ONDE:** `https://dashboard.stripe.com`

```
O toggle "Test mode" está:  [ ] ligado   [ ] desligado

Em modo LIVE, existem produtos cadastrados?  [ ] sim  [ ] não
Se sim, quantos price ativos por produto?  ______
```

⚠️ **Distinção que já enganou nesta auditoria:** o *toggle* do painel **não é**
o estado da conta. Já aconteceu de o toggle estar em Test enquanto a conta
tinha produtos **live** desde março. Olhe os dois.

**NÃO altere nada aqui.** Nem o toggle, nem produto, nem preço.

---

# Fim do diagnóstico

**Não avance para o Runbook B.** Leve as respostas para
[`CHECKPOINT.md`](CHECKPOINT.md).

O checkpoint é decisão do **dono do produto** — não do executor, não de um
agente. Se algum item ficar em "não", **o procedimento para ali** até haver
decisão escrita.

## Índice de respostas — o que cada passo alimenta

| Passo | Alimenta |
|---|---|
| A1 | `DATABASE_URL` conferida · valores antigos para rollback |
| A2 | fatura compreendida |
| A3 | serviço Live |
| A4 | **backup lógico disponível** |
| A5 · A6 | contexto para as decisões do Runbook B |
