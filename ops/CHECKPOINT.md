# Checkpoint — autorização para alterar produção

**Entre o diagnóstico e a execução existe uma decisão, e ela é humana.**

Este documento é assinado pelo **dono do produto**. Não por um agente, não pelo
executor, não por quem está com o painel aberto.

```
Diagnóstico  →  ►CHECKPOINT◄  →  Execução  →  Validação
(Runbook A)      (aqui)           (Runbook B)
```

**Enquanto este documento não estiver preenchido e assinado, o
[`RUNBOOK_B_EXECUCAO.md`](RUNBOOK_B_EXECUCAO.md) não roda.**

---

## Os quatro itens

Todos vêm do [`RUNBOOK_A_DIAGNOSTICO.md`](RUNBOOK_A_DIAGNOSTICO.md). Nenhum se
responde aqui — aqui só se registra e decide.

### 1 · `DATABASE_URL` conferida e salva
```
[ ] Copiada para gerenciador de senhas          (Runbook A, passo A1)
[ ] Contém "neon.tech"                          (A1)

Valor mascarado: postgresql:// … ______   (____ caracteres)
```
🔴 **Se não contiver `neon.tech`, PARE.** A aplicação está apontando para o
banco errado, e isso precede qualquer outra coisa.

### 2 · Fatura compreendida
```
[ ] Sei exatamente qual recurso gera a cobrança  (A2)

Recurso: ________________________  R$ ______

Decisão:  [ ] pagar    [ ] remover o recurso    [ ] outra: __________
Por quê:  ________________________________________________
```
⚠️ *"Está cobrando, então pago"* **não é decisão** — é ausência de decisão.
`PLANO_BACKEND` e `PLANO_DB_RENDER` são `free`, e serviço free não fatura. Se
não souber o que gera a cobrança, o item fica em **não**.

### 3 · Serviço Live
```
[ ] /health responde                             (A3)
[ ] "status": "ok"
[ ] "database": "connected"
```

### 4 · Backup lógico disponível
```
[ ] PITR do Neon confirmado                      (A4)

Retenção: ______ dias
```

**Se o PITR NÃO existir**, este item pode ficar em "não" e ainda assim liberar
— mas a decisão tem que ser **escrita**:

```
[ ] Aceito rodar o piloto SEM backup do banco.
    Entendo que, se o Neon falhar, os dados dos cinco usuários
    não são recuperáveis.
    Mitigação escolhida: ____________________________________
    Assinado: ______________  Data: ___/___/______
```

⚠️ **Alternativa antes de aceitar o risco:** peça a cada usuário do piloto que
use `GET /api/auth/export-my-data` no fim de cada dia. É backup do lado deles,
funciona hoje, e está testado. Não substitui PITR — mas transforma perda total
em perda de um dia.

---

## Valores antigos — para o rollback

Preenchido no passo **A1**. É daqui que o Runbook B tira o que restaurar se
algo der errado.

| Variável | Valor mascarado | Comprimento |
|---|---|---|
| `DATABASE_URL` | | |
| `STRIPE_SECRET_KEY` | | |
| `STRIPE_PRICE_ESSENCIAL` | | |
| `STRIPE_PRICE_PROFISSIONAL` | | |
| `STRIPE_PRICE_COMPLETO` | | |
| `STRIPE_WEBHOOK_SECRET` | | |
| `RESEND_API_KEY` | | |
| `EMAIL_FROM` | | |

⚠️ **Mascarado aqui; o valor inteiro fica no gerenciador de senhas.** Este
arquivo é versionado — segredo não entra nele.

---

## Assinatura

```
Todos os quatro itens estão resolvidos, ou têm decisão escrita
registrada acima. Autorizo a execução do RUNBOOK_B_EXECUCAO.md.

Assinado: ________________________
Data:     ___/___/______  Hora: ____:____
```

**A hora importa:** se algo der errado e for preciso restaurar por PITR, ela é
o ponto de retorno.

---

## Se algum item ficar em "não"

**O procedimento para.** Não existe "vou fazendo e resolvo depois" — cada um
dos quatro protege contra uma classe de dano diferente:

| Item em "não" | O que pode acontecer |
|---|---|
| `DATABASE_URL` não conferida | banco trocado por vazio, sem erro nenhum |
| Fatura não compreendida | pagar por recurso que devia ser removido |
| Serviço não Live | nada se verifica; qualquer mudança é às cegas |
| Sem backup lógico | perda de dados **irreversível** dos cinco usuários |

Registre o que faltou e o que precisa acontecer para destravar:

```
Item pendente: ____________________
O que falta:   ____________________
Quem resolve:  ____________________
```
