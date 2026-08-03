# Portão O — Operação

## Resultado

# ⛔ AINDA NÃO

**Data:** 02/08/2026

Tudo que depende de infraestrutura, conta paga e configuração de painel.
**Nenhum item aqui se prova por teste** — por isso não está em
[`PORTAO_A.md`](PORTAO_A.md), que já **PASSOU**.

> Se a resposta para *"por que não subiu?"* for **"falta pagar"**, **"falta a
> chave"** ou **"falta configurar"**, o item é deste documento. Sem essa
> separação, a equipe diz "não passou no Portão A" quando o que falta é uma
> fatura do provedor.

---

# ⚠️ CHECKLIST OBRIGATÓRIO — ANTES DE TOCAR NO PAINEL

**Faça isto uma vez, antes de qualquer alteração.** É o que torna todo
`COMO DESFAZER` deste documento possível: **não existe rollback sem o valor
antigo salvo.**

```
[ ] 1. Render → nexus-backend → Environment → abra a lista completa
[ ] 2. COPIE PARA O GERENCIADOR DE SENHAS, valor por valor:
         DATABASE_URL              ← o mais importante (começa com postgresql://…neon.tech)
         STRIPE_SECRET_KEY
         STRIPE_PRICE_ESSENCIAL
         STRIPE_PRICE_PROFISSIONAL
         STRIPE_PRICE_COMPLETO
         STRIPE_WEBHOOK_SECRET
         RESEND_API_KEY
         EMAIL_FROM
[ ] 3. Salve também o /health de agora (mesmo suspenso, guarde a resposta)
[ ] 4. Anote a data e a hora — o PITR do Neon, se existir, usa isso
```

**Regra que passa a valer (D-014):** nunca reaplicar blueprint em produção sem
validar antes as variáveis críticas. E, durante qualquer operação: **trabalhe
só pela aba Environment.**

---

## A mina do `DATABASE_URL`

`render.yaml`, linhas 28-31:

```yaml
- key: DATABASE_URL
  fromDatabase:
    name: nexus-db          # ← Postgres FREE do Render
    property: connectionString
```

**O banco de produção é o Neon, não o `nexus-db`.** O valor verdadeiro existe
**apenas no painel**, colado à mão quando a migração foi feita.

**O risco:** o botão de reaplicar o blueprint (`Sync` / `Reapply`) fica a um
clique de distância de onde você vai mexer. Se ele for acionado, o
`DATABASE_URL` volta a apontar para o `nexus-db` — **um banco diferente e
vazio**. A aplicação sobe normalmente, o `/health` diz `database: connected`,
e todos os dados somem de vista.

**O que fazer:**

1. **Antes de qualquer coisa**, no Render → `nexus-backend` → **Environment**,
   copie o valor atual de `DATABASE_URL` para um lugar seguro (gerenciador de
   senhas). É o endereço do Neon, começa com `postgresql://…neon.tech…`
2. **Nunca** clique em `Sync`, `Reapply blueprint` ou `Apply changes` no
   Blueprint durante esta operação
3. Trabalhe **só** pela aba **Environment** do serviço

**Como saber se aconteceu:** o `/health` continua `ok`, mas você faz login e
**não existe nenhum dado**. Se isso ocorrer, recole o valor salvo no passo 1.

> O próprio `render.yaml` avisa sobre essa classe de problema nas linhas 82-86,
> para as outras variáveis: *"um reapply do blueprint devolveria o serviço ao
> estado quebrado"*. **Esta continua lá.**

---

# Os 5 bloqueadores

---

## 1 · Render ativo

**O QUE É** — Os serviços que hospedam a API e o site estão suspensos por
inadimplência.

**POR QUE BLOQUEIA** — `api.nexxusapp.com.br` e `app.nexxusapp.com.br`
respondem *"This service has been suspended"*. Sem isto **nada abaixo se
verifica** — nem o Stripe, nem o e-mail, nem o PITR. E nenhum usuário entra.

**ONDE** — `https://dashboard.render.com/billing`

### 🟠 Antes de pagar: descubra o que está sendo cobrado

`render.yaml` declara **`plan: free`** no backend (linha 6) **e** no banco
(linha 140). **Serviço free não gera fatura.** Então há algo mais na conta.

Hipóteses, em ordem de probabilidade:

| Causa | Como confirmar |
|---|---|
| **Postgres free expirou** — o Render dá 90 dias e depois exige plano pago | Dashboard → `nexus-db` → veja se diz *expired* ou pede upgrade |
| **Recurso órfão** de outra época (serviço duplicado, disco, cron) | Dashboard → lista de serviços — algum que você não reconhece? |
| Upgrade de plano feito e esquecido | Billing → Invoices → abra a última fatura e leia as linhas |

⚠️ **O `nexus-db` provavelmente não é mais usado** — o banco real é o Neon. Se
a cobrança for dele, a resposta certa pode ser **deletar**, não pagar.
**Remover recurso não usado é melhor que pagar por ele.**

**O QUE FAZER**

1. Billing → **Invoices** → abra a fatura em aberto e **leia as linhas**
2. Identifique qual recurso gera a cobrança
3. Se for recurso que você não usa: **Suspend** primeiro (reversível), confirme
   que nada quebrou, e só então **Delete**
4. Se for legítimo: regularize o pagamento
5. Aguarde os serviços voltarem a **Live**

**COMO VERIFICAR**

```bash
curl -s https://api.nexxusapp.com.br/health
```

Resposta certa — o `status` e o `database` são o mínimo:

```json
{ "status": "ok", "database": "connected" }
```

**SE DER ERRADO**

| Sintoma | Significa |
|---|---|
| `This service has been suspended` | ainda não reativou |
| `"database": "error"` | subiu, mas não alcança o banco → confira `DATABASE_URL` |
| `502` / `503` | está subindo ainda, ou o boot falhou → veja **Logs** |
| Boot falha com `Variaveis de ambiente CRITICAS ausentes` | faltou `DATABASE_URL` ou `JWT_SECRET` — são as duas únicas que **derrubam o boot** |

**COMO DESFAZER**

Pagamento não se desfaz. O que se desfaz é o **dano colateral** de mexer no
painel:

| Se aconteceu | Restaure | Onde acha o valor | Confirme |
|---|---|---|---|
| Deletou recurso errado | — | ⚠️ **Delete não tem volta no Render** | por isso o passo 3 manda **Suspend primeiro** |
| `DATABASE_URL` mudou | `DATABASE_URL` | checklist pré-painel, item 2 | login → **seus dados aparecem** |
| Reaplicou o blueprint | **todas** as `sync: false` | checklist pré-painel | `/health` → `degradadas_faltando: []` |

**Tempo:** cada Save dispara um redeploy — **2 a 5 minutos** até voltar a
`Live`. Não salve em sequência: aguarde o anterior terminar.

---

## 2 · Stripe em modo live

**O QUE É** — A chave de produção é de **teste**. O checkout aceita cartão de
teste e **nenhum dinheiro real entra**.

**POR QUE BLOQUEIA** — Sem chave live não existe primeira venda. E o
`/health` já acusa: `config.stripe.autentica: false`.

**ONDE** — `https://dashboard.stripe.com` (⚠️ com o toggle **Test mode
DESLIGADO**) e depois Render → `nexus-backend` → **Environment**

**O QUE FAZER**

1. Stripe → canto superior → **desligue** *Test mode*
2. Developers → **API keys** → **Reveal live key** → copie a `sk_live_…`
3. Render → `nexus-backend` → **Environment**
4. Edite as **quatro** variáveis abaixo
5. **Um único Save** — o Stripe recusa misturar chave live com price de teste,
   então salvar em duas etapas deixa o sistema quebrado no intervalo

**VALOR EXATO**

```
STRIPE_SECRET_KEY          = sk_live_…              (do painel, passo 2)
STRIPE_PRICE_ESSENCIAL     = price_1TFtcdRwnNMZfuJ2Yfub1J0S     R$ 29,90
STRIPE_PRICE_PROFISSIONAL  = price_1TFteFRwnNMZfuJ2mi7OS4n2     R$ 59,90
STRIPE_PRICE_COMPLETO      = price_1TFtfmRwnNMZfuJ2PToTrk6O     R$ 89,90
```

⚠️ **Confira caractere a caractere.** Existem **duas gerações** de preço na
conta: a antiga (39,90 / 69,90 / 99,90) e a atual. Um ID errado aqui **cobra o
valor errado de um cliente real e o sistema não tem como saber** — do ponto de
vista do Stripe está tudo correto.

**COMO VERIFICAR**

```bash
curl -s https://api.nexxusapp.com.br/health
```

```json
"config": {
  "stripe": {
    "autentica": true,
    "motivo": "chave valida (modo live)",
    "precos_coerentes": true
  }
}
```

Os dois campos importam por motivos diferentes:
- **`autentica`** — a chave **cobra**? (chave existir não basta; já houve uma
  que existia e era rejeitada — E-029)
- **`precos_coerentes`** — cada `STRIPE_PRICE_*` existe **no mesmo modo da
  chave**? Pega o erro clássico de `sk_live_` com price de teste

**SE DER ERRADO**

| `motivo` diz | Significa |
|---|---|
| `chave REJEITADA pelo Stripe` | copiou errado, revogada, ou é de outra conta |
| `chave valida (modo test)` | esqueceu de desligar o *Test mode* antes de copiar |
| `precos_coerentes: false` | price de teste com chave live (ou o contrário) |
| `indeterminado: falha de rede` | blip de rede, **não** é chave ruim — repita |

Na página de planos, o banner **"Sistema de pagamento em manutenção"** some
quando isto passa. Ele nunca foi modo de manutenção: é o sintoma de chave que
não autentica.

**COMO DESFAZER**

```
Restaurar:  as 4 variáveis, de volta aos valores de teste
Onde achar: checklist pré-painel, item 2
Como:       UM ÚNICO SAVE com as 4 juntas (mesma regra da ida — D-015)
Esperar:    2 a 5 min (redeploy)
Validar:    /health → config.stripe.autentica: true, motivo "modo test"
```

⚠️ **Não desfaça pela metade.** Voltar só a chave e deixar os price live (ou o
contrário) deixa `precos_coerentes: false` — pior que qualquer um dos dois
estados inteiros.

🟢 **Reversível sem consequência**, *desde que ninguém tenha pago ainda*. Se já
houver assinatura live, voltar para teste **não cancela a cobrança** — ela
continua no Stripe e o NEXUS deixa de enxergá-la. A partir da primeira venda,
isto deixa de ser rollback e vira migração.

---

## 3 · Webhook do Stripe em modo live

**O QUE É** — O aviso que o Stripe manda quando alguém paga. É ele que ativa
o plano no NEXUS.

**POR QUE BLOQUEIA** — 🔴 **É o pior modo de falha possível com cliente real:
ele paga e não recebe acesso.** O código está testado (`604a207`,
`test_caminho_do_dinheiro.py`); falta o endpoint existir em live.

**ONDE** — `https://dashboard.stripe.com/webhooks` (⚠️ **Test mode
DESLIGADO**)

**O QUE FAZER**

1. **Add endpoint**
2. URL — exatamente esta:
   ```
   https://api.nexxusapp.com.br/api/auth/webhook
   ```
3. Selecione **os 6 eventos** (lidos de `_stripe_webhook_handler.py:495-502` —
   são exatamente os que o código trata):
   ```
   checkout.session.completed
   invoice.paid
   invoice.payment_failed
   charge.refunded
   customer.subscription.updated
   customer.subscription.deleted
   ```
4. Salve → copie o **Signing secret** (`whsec_…`)
5. Render → `nexus-backend` → Environment → `STRIPE_WEBHOOK_SECRET` = o
   `whsec_` → **Save**

⚠️ **Existem duas rotas de webhook** no backend, e **as duas funcionam**:
`/api/auth/webhook` e `/api/auth/webhook/stripe`. Use a primeira — é a mesma
que o endpoint de *test* já usa, e assim live e test ficam consistentes.

**COMO VERIFICAR**

Só um pagamento real prova. **O teste de efeito, com cartão de verdade:**

1. Crie uma conta nova em `app.nexxusapp.com.br`
2. Assine o **Essencial**
3. Confira **três coisas**:

| # | O quê | Onde |
|---|---|---|
| a | Cobrou **R$ 29,90** — não 39,90 | tela do checkout |
| b | A assinatura aparece em **live** | Stripe → Subscriptions |
| c | **O plano do usuário mudou** no NEXUS | perfil, ou `/api/auth/me` |

**O (c) é o que prova que o webhook chegou.** Se (a) e (b) passarem e (c)
falhar, o webhook live não está configurado — e é exatamente o cenário do
pagamento sem acesso.

Do lado do NEXUS: `GET /api/admin/billing/webhook-stats` (exige login admin)
mostra se algum evento chegou a ser processado.

**SE DER ERRADO**

| Sintoma | Significa |
|---|---|
| Stripe mostra entrega com `400 Assinatura invalida` | o `whsec_` no Render não bate com o do endpoint |
| Entregas com `200` mas o plano não muda | o handler falhou — veja Sentry e `WebhookHit.error` |
| Nenhuma entrega listada | o endpoint não foi acionado — confira a URL |

⚠️ **Detalhe que engana:** o handler devolve **200 mesmo quando falha**
(`_stripe_webhook_handler.py:602`, com comentário explícito), para o Stripe não
reenviar em duplicata. **Ver `200` no painel do Stripe não prova que deu
certo.** Só o (c) prova.

**COMO DESFAZER**

```
Desfazer:   Stripe → Webhooks → o endpoint → Disable (não Delete)
            Render → STRIPE_WEBHOOK_SECRET → valor antigo
Onde achar: checklist pré-painel, item 2
Esperar:    2 a 5 min (redeploy)
Validar:    /health → degradadas_faltando NÃO lista STRIPE_WEBHOOK_SECRET
```

**Disable, não Delete** — desabilitado guarda o histórico de entregas, que é o
que você vai querer ler se algo deu errado.

🟠 **Enquanto o endpoint estiver desabilitado, pagamento não ativa plano.** Se
alguém pagar nessa janela, o Stripe guarda o evento: reabilite e use
**Resend** na entrega que falhou. Do lado do NEXUS existe
`POST /api/admin/billing/resync-invoices` para reconciliar.

---

## 4 · Backup do banco — PITR do Neon

**O QUE É** — *Point-in-time recovery*: a capacidade de voltar o banco a um
momento anterior.

**POR QUE BLOQUEIA** — A frase-objetivo do piloto é literal: *"cinco usuários
trabalham sete dias **sem perder dados**"*. Perder o cadastro de um MEI na
primeira semana custa a confiança que o piloto existe para medir.

**ONDE** — `https://console.neon.tech` → projeto `nexus` → **Settings**

**O QUE FAZER** — Não é configuração, é **pergunta**. Responda duas:

1. **O plano atual inclui PITR?** (o free tier do Neon costuma incluir, com
   janela curta)
2. **Qual a retenção, em dias?**

Anote as respostas na tabela abaixo. Isso vira a linha de evidência deste item.

```
PITR incluído:  [ ] sim   [ ] não
Retenção:       ____ dias
Verificado em:  ___/___/______
```

**SE A RESPOSTA FOR "NÃO"** — aí sim vira **trabalho de engenharia**, e volta
para o Portão A: um dump agendado para armazenamento externo. Só faça isso se
a resposta for não — credencial nova e job novo, para cinco usuários em sete
dias, protegem menos do que arriscam.

**O QUE JÁ ESTÁ RESOLVIDO** — a metade do **usuário**. `GET
/api/auth/export-my-data` devolve perfil, clientes, oportunidades,
agendamentos e resumo financeiro. Testado (`test_backup_exportacao.py`, 5
testes) e **está no Portão A**.

> ⚠️ Isso **não** é backup do banco. Se o Neon cair sem PITR, a exportação não
> recupera nada — ela garante que o usuário tinha como tirar cópia enquanto o
> sistema estava de pé. São coisas diferentes.

**COMO DESFAZER**

Este passo é **só leitura** — não há o que desfazer. Ninguém muda nada no Neon
aqui; a resposta é uma anotação.

⚠️ **A exceção perigosa:** se em algum momento você **restaurar** o banco por
PITR, isso **descarta tudo que aconteceu depois do ponto escolhido**. Restaurar
não é rollback barato — é a última opção, e o custo é o trabalho dos usuários
desde aquele instante.

**Antes de restaurar, sempre:** anote a hora exata do incidente, e prefira
restaurar para um **branch novo** do Neon (ele suporta), comparar, e só então
promover. Restaurar por cima do banco vivo é irreversível.

---

## 5 · E-mail transacional

**O QUE É** — O envio real de e-mail. Hoje serve a recuperação de senha.

**POR QUE BLOQUEIA** — Um usuário que esquece a senha e não recebe o e-mail
**perde a conta**. Não há outro caminho de volta.

**ONDE** — `https://resend.com` + o DNS de `nexxusapp.com.br` + Render →
Environment

**O QUE FAZER**

1. Resend → **API Keys** → crie ou confirme a chave (`re_…`)
2. Resend → **Domains** → o domínio `nexxusapp.com.br` está **Verified**?
3. Se não: adicione os registros **SPF** e **DKIM** que o Resend indica no DNS
   do domínio, e aguarde a verificação
4. Render → Environment:
   ```
   RESEND_API_KEY = re_…
   EMAIL_FROM     = NEXUS <contato@nexxusapp.com.br>
   ```

⚠️ **Três formas de a chave existir e o e-mail não sair** — todas já
observadas nesta auditoria:

| Causa | Sintoma no log |
|---|---|
| domínio **não verificado** no Resend | nada sobre Resend, e o e-mail não chega |
| `EMAIL_FROM` com `@gmail.com` | o Resend **recusa** — domínio não é seu |
| pacote `resend` não instalado no build | `Pacote 'resend' nao instalado` |

O default de `EMAIL_FROM` é `@gmail.com`. **Configurar a chave sem trocar isso
não resolve nada.**

**COMO VERIFICAR** — teste de **efeito**, não de configuração:

1. `app.nexxusapp.com.br` → login → **"Esqueceu a Senha?"**
2. Digite **seu e-mail de verdade**
3. Abra o Gmail — **inclusive a pasta Spam**

**O e-mail chegou, sim ou não?** É a única pergunta que importa. Ler a chave no
painel não prova nada.

**SE DER ERRADO** — Render → `nexus-backend` → **Logs** → busque `RESEND`. A
tabela acima traduz cada mensagem.

**COMO DESFAZER**

```
Restaurar:  RESEND_API_KEY e EMAIL_FROM aos valores antigos
Onde achar: checklist pré-painel, item 2
Esperar:    2 a 5 min (redeploy)
Validar:    Logs → nenhum CRITICAL de RESEND no boot
```

🟢 **Registro de DNS não precisa ser desfeito.** SPF e DKIM do Resend não
atrapalham nada se ficarem lá — e você vai precisar deles de volta na próxima
tentativa. Deixe.

⚠️ **Com `RESEND_API_KEY` ausente, `forgot-password` responde 503** em vez de
mentir *"enviamos"*. É o comportamento correto (foi corrigido de propósito) —
mas significa que **a recuperação de senha fica indisponível** enquanto o
rollback durar. Avise os cinco usuários se acontecer.

---

# Não bloqueia o piloto, mas registrar

### Domínio, DNS e HTTPS
```
Estado:    ✅ funcionavam antes da suspensão
Verificar: https://app.nexxusapp.com.br carrega com cadeado
```

### Monitoramento
```
Sentry:  ✅ ativo antes da suspensão (/health → "sentry": "active")
Falta:   alerta que avise VOCÊ quando /health parar de responder
```
Hoje a descoberta de que o sistema caiu seria **por um usuário reclamando**.
Com cinco usuários acompanhados de perto isso é tolerável; com cinquenta, não.

### Disaster Recovery
```
Estado: ⛔ NUNCA DISCUTIDO — e é diferente de backup
```

| | Responde |
|---|---|
| **Backup** | *"os dados existem em outro lugar?"* |
| **DR** | *"em quanto tempo o serviço volta, e quem faz?"* |

Para cinco usuários em sete dias, o risco é aceitável. Fica **escrito**, não
esquecido.

---

# Verificação final — um comando

Quando os 5 estiverem resolvidos:

```bash
curl -s https://api.nexxusapp.com.br/health
```

Resposta que fecha o Portão O:

```json
{
  "status": "ok",
  "database": "connected",
  "sentry": "active",
  "config": {
    "environment": "production",
    "status": "ok",
    "criticas_faltando": [],
    "degradadas_faltando": [],
    "stripe": { "autentica": true, "precos_coerentes": true },
    "automacao_web": { "disponivel": true }
  }
}
```

**Campo a campo:**

| Campo | Errado significa |
|---|---|
| `criticas_faltando` não vazio | `DATABASE_URL` ou `JWT_SECRET` — o boot nem deveria ter subido |
| `degradadas_faltando` não vazio | lista **os nomes** que faltam — Stripe, Resend, `ADMIN_EMAILS`, `TAX_REGIME` |
| `stripe.autentica: false` | a chave não cobra |
| `stripe.precos_coerentes: false` | price de modo diferente da chave |
| `automacao_web.disponivel: false` | chromium ausente — **não bloqueia**, mas não prometer automação na oferta |

**E o teste de efeito, que nenhum `/health` substitui:** uma compra real de
R$ 29,90 que muda o plano do usuário.

---

# Os dois `SKIPPED` da suíte

Prova de que a fronteira A/O é real e não convenção. Dos 521 testes do Portão
A, os dois únicos pulados são:

```
test_caminho_do_dinheiro.py::test_webhook_recusa_assinatura_invalida
  → STRIPE_WEBHOOK_SECRET ausente          (bloqueador 3)

test_forgot_password_integracao.py
  → pacote 'resend' nao instalado          (bloqueador 5)
```

**A suíte de engenharia só não consegue verificar aquilo que não é
engenharia.** Quando os bloqueadores 3 e 5 fecharem, os dois deixam de pular.

---

# Ordem de execução

1. **Render** — sem isto nada mais se verifica *(e descubra o que está sendo
   cobrado antes de pagar)*
2. **Stripe live** — as 4 envs num Save só
3. **Webhook live** — os 6 eventos + `whsec_`
4. **PITR do Neon** — pergunta de painel; se não existir, vira engenharia
5. **E-mail** — o e-mail chega ou não chega
6. → **os cinco usuários entram**

---

## O que este documento NÃO é

Não é lista de melhorias. Item entra aqui só se **impedir cinco pessoas de usar
o produto por sete dias** — o mesmo filtro do Portão A, aplicado ao que não é
código.
