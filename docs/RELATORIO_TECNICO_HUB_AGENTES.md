# Relatório Técnico — Hub de Agentes NEXUS

**Data**: Julho 2025  
**Commit base**: `3c450b3` (branch `main`)  
**Método**: Leitura direta de todo código-fonte relevante. Nenhuma capacidade foi inventada.

---

## Índice

1. [Inventário Completo dos Agentes](#1-inventário-completo-dos-agentes)
2. [Capacidades Individuais por Agente](#2-capacidades-individuais-por-agente)
3. [Capacidades Integradas (Fluxos Inter-Agentes)](#3-capacidades-integradas)
4. [Prompts de Teste Recomendados](#4-prompts-de-teste-recomendados)
5. [Lacunas Identificadas](#5-lacunas-identificadas)

---

## 1. Inventário Completo dos Agentes

### 1.1 Visão Geral

O NEXUS possui **5 agentes ativos** com identidade própria, mais **2 módulos legados** que são usados como bibliotecas internas. Todos são orquestrados pelo endpoint central `POST /api/agents/{agent_id}/execute`.

| # | ID | Nome | Arquivo de Classe | Arquivo de Prompt | Linhas |
|---|-----|------|-------------------|-------------------|--------|
| 1 | `agenda` | Assistente de Agenda | `backend/agents/agenda_agent.py` | `backend/app/api/agent_chat.py` | 408 |
| 2 | `clientes` | Assistente de Clientes | `backend/agents/clients_agent.py` | `backend/app/api/agent_chat.py` | 505 |
| 3 | `contabilidade` | Assistente Financeiro | `backend/agents/contabilidade_agent.py` | `backend/app/api/agent_chat.py` | 1156 |
| 4 | `cobranca` | Assistente de Cobranças | `backend/agents/collections_agent.py` | `backend/app/api/agent_chat.py` | 65 |
| 5 | `assistente` | Assistente Geral | *(wrapper inline no router)* | `backend/app/api/agent_chat.py` | — |
| — | *(legado)* | Finance Agent | `backend/agents/finance_agent.py` | — | 589 |
| — | *(legado)* | NF Agent | `backend/agents/nf_agent.py` | — | 129 |

**Aliases legados**: `"financeiro" → "contabilidade"`, `"documentos" → "contabilidade"` (mapeados em `_AGENT_ID_ALIAS` e `_alias` no agent_chat).

### 1.2 Endpoints por Agente

Todos os agentes compartilham os mesmos endpoints sob `/api/agents`:

| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| POST | `/{agent_id}/execute` | **Endpoint principal** — executa ação (chat, quick action, automação) | JWT |
| GET | `/{agent_id}/config` | Configuração do agente | JWT |
| PUT | `/{agent_id}/config` | Atualiza configuração | JWT |
| GET | `/{agent_id}/status` | Status detalhado | ⚠️ Sem auth |
| GET | `/list` | Lista os 5 agentes | JWT |

**Endpoints do Hub (inter-agentes)**:

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/hub/status` | Status do hub e agentes registrados |
| GET | `/hub/messages?limit=50` | Mensagens recentes do hub |
| POST | `/hub/message` | Envia mensagem entre agentes |
| POST | `/hub/workflow` | Executa workflow (`novo_cliente`, `cobranca`) |
| GET | `/hub/context` | Contexto compartilhado |
| POST | `/hub/sync` | Re-sincroniza agentes |

**Endpoints de Mídia**:

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/audio/transcribe` | Transcreve áudio via Whisper → envia ao agente |
| POST | `/upload` | Upload de imagem/PDF/CSV/doc → processa → envia ao agente |

**Endpoints de Automação Web**:

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/automation/start` | Gera plano de automação |
| POST | `/automation/approve` | Aprova/rejeita plano |
| GET | `/automation/status/{task_id}` | Status da automação |

**Endpoints de Chat e Analytics**:

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/chat/history/{agent_id}` | Histórico de chat |
| POST | `/api/chat/save` | Salva mensagem |
| DELETE | `/api/chat/history/{agent_id}` | Limpa histórico |
| GET | `/api/analytics/dashboard` | Dashboard consolidado |
| GET | `/api/analytics/activity` | Timeline de atividades |

### 1.3 System Prompts

Cada agente possui um system prompt dedicado em `AGENT_SYSTEM_PROMPTS` (arquivo `agent_chat.py`). Todos incluem:

- **Guardrail anti-alucinação**: Bloco `╔══ REGRA ABSOLUTA — PROIBIDO INVENTAR DADOS ══╝` no topo
- **Dados reais injetados**: Placeholder `{crm_context}` preenchido com dados do banco via `_get_crm_context(user_id)`
- **Data atual**: Placeholder `{date}` com `datetime.now()`
- **Idioma**: Português brasileiro mandatório

| Agente | Foco do Prompt | Tamanho |
|--------|----------------|---------|
| `agenda` | Marcar compromissos, lembretes, prazos fiscais, reagendamento | ~40 linhas |
| `clientes` | Cadastro, busca, listagem, follow-up, aniversários. Proíbe scores/probabilidades | ~50 linhas |
| `contabilidade` | DAS, DASN, NF, limite MEI, multas, entradas/saídas. Inclui valores 2026 reais | ~55 linhas |
| `cobranca` | Devedores, mensagens por faixa de atraso (1-3d, 4-7d, 8-15d, 16d+) | ~40 linhas |
| `assistente` | Resumo geral, sugestões, alertas. Inclui instrução explícita sobre automação web | ~45 linhas |

### 1.4 Quick Actions (ACTION_PROMPTS)

Botões pré-mapeados no frontend que convertem cliques em prompts naturais:

| Agente | Ação | Prompt Enviado ao LLM |
|--------|------|----------------------|
| **Agenda** | `list_today` | "O que eu tenho marcado pra hoje?" |
| | `list_week` | "Mostra minha agenda da semana." |
| | `add_appointment` | "Quero marcar um compromisso. Me pergunta o dia, hora e o que vou fazer." |
| | `list_reminders` | "Quais são meus lembretes?" |
| **Clientes** | `list_clients` | "Mostra meus clientes. Lista simples com nome, telefone e se tá ativo." |
| | `add_client` | "Quero cadastrar um cliente novo. Me pergunta nome, telefone e email." |
| | `search_client` | "Quero procurar um cliente. Me pergunta o nome ou telefone." |
| | `list_followup` | "Quais clientes eu preciso entrar em contato?" |
| | `pipeline_summary` | "Me mostra um resumo das minhas vendas..." |
| **Contabilidade** | `monthly_summary` | "Como tá meu mês? Quanto entrou, quanto saiu e quanto sobrou." |
| | `get_balance` | "Qual meu saldo?" |
| | `mei_status` | "Como tá meu limite do MEI?" |
| | `das_status` | "Quando vence meu DAS?" |
| | `dasn_status` | "Preciso fazer a declaração anual (DASN)?" |
| | `calendario_fiscal` | "Quais são minhas obrigações fiscais?" |
| | `checklist_mensal` | "O que eu preciso fazer esse mês?" |
| | `emit_nf` | "Quero emitir uma Nota Fiscal." |
| | `list_nf` | "Mostra as notas fiscais que emiti esse mês." |
| | `irpf_calculo` | "Como funciona meu imposto de renda como MEI?" |
| | `generate_report` | "Quais relatórios eu posso ver?" |
| | `generate_contract` | "Quero fazer um contrato." |
| | `penalidades` | "O que acontece se eu atrasar o DAS ou a DASN?" |
| **Cobrança** | `list_overdue` | "Quem tá devendo?" |
| | `list_pending` | "Quem vai ter que pagar nos próximos 7 dias?" |
| | `send_reminder` | "Quero cobrar um cliente." |
| | `total_open` | "Quanto eu tenho pra receber no total?" |
| **Assistente** | `daily_summary` | "Me dá um resumo do meu dia." |
| | `suggest_tasks` | "O que é mais importante eu fazer agora?" |
| | `get_alerts` | "Tem algum alerta importante?" |
| | `help` | "Explique todas as minhas capacidades, incluindo automação web." |
| | `web_automation` | "O usuário quer usar a automação web..." |

**Total: 30 quick actions** mapeadas.

### 1.5 Acesso ao Banco de Dados por Agente

| Agente | Lê do DB? | Escreve no DB? | Via qual serviço? | O que acessa? |
|--------|-----------|----------------|-------------------|---------------|
| `agenda` | **NÃO** | **NÃO** | — | Processa JSON em memória |
| `clientes` | **NÃO** | **NÃO** | — | Processa JSON em memória |
| `contabilidade` | **SIM** | **NÃO** | `CRMService.get_financial_summary()` | Receitas, despesas, lucro do mês |
| `cobranca` | **NÃO** | **NÃO** | — | Carrega de arquivo JSON |
| `assistente` | **NÃO** | **NÃO** | — | Wrappers inline |
| *(via LLM flow)* | **SIM** | **SIM** | `CRMService` + `ChatMessage` | Todos: CRM context é injetado no prompt; mensagens são salvas |

**Nota importante**: A maioria dos agentes (as classes em `backend/agents/`) **não acessa o banco diretamente**. O acesso real ao banco acontece no **fluxo LLM** (`agent_chat.py` e `agent_hub.py` API router):

1. `_get_crm_context(user_id)` → chama `CRMService` para buscar: clientes, faturas vencidas, faturas próximas, agendamentos, transações, aniversariantes
2. O resultado é injetado como texto no `{crm_context}` do system prompt
3. O LLM vê os dados e responde com base neles
4. As mensagens (user + assistant) são salvas em `ChatMessage`

### 1.6 Dados Injetados via `_get_crm_context(user_id)`

| Dado | Método do CRMService | Limite |
|------|----------------------|--------|
| Clientes ativos | `search_clients(is_active=True, limit=20)` | 20 |
| Faturas vencidas | `get_overdue_invoices()` | Todas |
| Faturas próximas | `get_upcoming_invoices(days=7)` | 7 dias |
| Agendamentos | `get_appointments(start, end)` | Hoje + 7 dias |
| Transações do mês | `get_financial_summary(month, year)` | Mês corrente |
| Clientes aniversariantes | `get_birthday_clients(days_ahead=7)` | 7 dias |
| Follow-up necessário | `get_clients_for_followup(days_inactive=7)` | 7 dias inativos |

### 1.7 Limites por Plano

| Recurso | Free | Essencial (R$39,90) | Profissional (R$69,90) | Completo (R$99,90) |
|---------|------|---------------------|------------------------|--------------------|
| **Agentes disponíveis** | `contabilidade` apenas | `contabilidade`, `clientes`, `cobranca` | Todos os 5 | Todos os 5 |
| **Mensagens/dia** | 10 | 200 | 1.000 | Ilimitado |
| **Clientes CRM** | 5 | 100 | 500 | Ilimitado |
| **Faturas/mês** | 3 | Ilimitado | Ilimitado | Ilimitado |

**Aliases de plano**: `pro → essencial`, `enterprise → completo`  
**Isenções**: Admins e superadmins não têm limites.

### 1.8 Respostas Anti-Alucinação (`_EMPTY_DATA_RESPONSES`)

Respostas pré-definidas retornadas **sem chamar o LLM** quando o CRM está vazio:

| Agente | Triggers | Resposta Resumida |
|--------|----------|-------------------|
| `contabilidade` | "mês", "DAS", "limite", "cobrança", "pagamento", "nota fiscal", "saldo" | Resposta explicando que não há dados + convite para cadastrar |
| `clientes` | "clientes", "cadastrar", "follow-up", "vendas" | "Você ainda não tem clientes cadastrados..." |
| `agenda` | "hoje", "semana", "marcar" | "Agenda limpa! Quer marcar algo?" |
| `cobranca` | "devendo", "pagamento", "cobrar", "receber" | "Não encontrei cobranças pendentes." |
| `assistente` | "resumo", "prioridade", "alerta" | "Ainda não tem informações cadastradas..." |

---

## 2. Capacidades Individuais por Agente

### 2.1 Agente: Agenda (`agenda`)

**Classe**: `AgendaAgent` em `backend/agents/agenda_agent.py` (408 linhas)

#### O que FAZ (implementado no código):
- **Processar obrigações fiscais**: Recebe JSON de obrigações, organiza por tipo e urgência
- **6 tipos de compromisso**: `fiscal`, `payment`, `invoice`, `supplier`, `purchase`, `deadline`
- **Cálculo de urgência**: `overdue` (vencido) → `today` → `critical` (1-2 dias) → `urgent` (3-5 dias) → `soon` (6-14 dias) → `normal` (15+ dias)
- **Calendário fiscal**: Monta calendário com prazos do mês
- **Agendamentos**: Cria/lista compromissos (via `execute()`)

#### O que FAZ via LLM (prompt + CRM context):
- Marcar compromissos com data, hora e descrição
- Listar agenda do dia e da semana (dados reais do banco)
- Avisar sobre prazos fiscais (DAS dia 20, DASN até 31/maio)
- Sugerir horários quando há conflito
- Criar lembretes

#### O que NÃO FAZ (não implementado):
- ❌ **Não envia notificações** (sem integração com email/WhatsApp/push)
- ❌ **Não sincroniza com Google Calendar** (sem integração)
- ❌ **Não reagenda automaticamente** (apenas sugere via LLM)
- ❌ **Não tem recorrência** (compromissos são pontuais)
- ❌ A classe `AgendaAgent` não acessa o banco — o acesso é indireto via CRM context no prompt

#### DB: O que o agente vê
- Agendamentos dos próximos 7 dias (via `_get_crm_context`)
- Zero acesso direto ao banco na classe

---

### 2.2 Agente: Clientes (`clientes`)

**Classe**: `ClientsAgent` em `backend/agents/clients_agent.py` (505 linhas)

#### O que FAZ (implementado no código):
- **4 ações**: `create`, `schedule`, `analyze`, `update`
- **Cálculo de scores** (métodos internos, não expostos no prompt):
  - `_calculate_purchase_score(total_purchases, avg_ticket, last_purchase_days)` → 0-100
  - `_calculate_attendance_score(total_appointments, no_shows)` → 0-100
  - `_calculate_churn_risk(days_since_last_interaction, purchase_frequency)` → 0-100%
  - `_calculate_engagement_score(interactions_count, days_as_client)` → 0-100
- **Processamento in-memory**: Não acessa banco diretamente

#### O que FAZ via LLM (prompt + CRM context):
- Cadastrar clientes (nome, telefone, email)
- Buscar por nome ou telefone
- Listar clientes (formato simples, sem scores visíveis)
- Identificar quem precisa de follow-up (inativos há 7+ dias)
- Lembrar aniversários (próximos 7 dias)
- Resumo de pipeline de vendas

#### O que NÃO FAZ (não implementado):
- ❌ **Scores não são exibidos ao usuário** (prompt proíbe explicitamente)
- ❌ **Não importa clientes em massa** (sem upload CSV → CRM)
- ❌ **Não envia mensagens para clientes** (sem integração WhatsApp/email)
- ❌ **Não tem segmentação automática** (segmento é manual)
- ❌ **Não gera relatórios de clientes** (apenas lista)
- ❌ A classe `ClientsAgent` não acessa o banco — o acesso é indireto via CRM context

#### DB: O que o agente vê
- 20 clientes ativos (via `_get_crm_context`)
- Clientes com follow-up pendente (inativos há 7+ dias)
- Aniversariantes (próximos 7 dias)

---

### 2.3 Agente: Contabilidade (`contabilidade`)

**Classe**: `ContabilidadeAgent` em `backend/agents/contabilidade_agent.py` (1156 linhas)

Este é o **maior e mais completo agente** do sistema. Também responde pelos IDs legados `financeiro` e `documentos`.

#### O que FAZ (implementado no código):

**25 ações na classe**:

| Ação | Descrição | Acessa DB? |
|------|-----------|------------|
| `analyze_month` | Análise financeira mensal (receita, despesa, lucro, margem, top categorias) | **SIM** via CRMService |
| `compare_months` | Comparação entre dois meses | **SIM** |
| `das_status` | Status do DAS (valor, vencimento, com base no tipo de atividade) | NÃO (constantes) |
| `dasn_status` | Status da DASN-SIMEI (prazo, como fazer) | NÃO (constantes) |
| `mei_status` | Uso do limite MEI R$81.000 (percentual, projeção) | **SIM** |
| `check_desenquadramento` | Verifica risco de desenquadramento (20% de tolerância) | **SIM** |
| `calendario_fiscal` | Calendário com 15 obrigações fiscais do ano | NÃO (constantes) |
| `checklist_mensal` | Checklist mensal (DAS, NFs, conciliação) | **SIM** parcial |
| `checklist_anual` | Checklist anual (DASN, IRPF, RAIS) | NÃO |
| `calcular_multa_das` | Calcula multa por atraso (0,33%/dia até 20% + SELIC) | NÃO (fórmula) |
| `calcular_multa_dasn` | Calcula multa DASN (2%/mês, mínimo R$50) | NÃO (fórmula) |
| `prepare_invoice` | Prepara dados para emissão de NFS-e | NÃO |
| `generate_contract` | Gera estrutura de contrato de prestação de serviços | NÃO |
| `generate_report` | Lista tipos de relatórios disponíveis | NÃO |
| `health_check` | Saúde financeira simplificada | **SIM** |
| `set_activity_type` | Define tipo de atividade MEI (commerce/services/both) | NÃO (in-memory) |
| `irpf_calculo` | Instruções sobre IRPF para MEI | NÃO |
| `obrigacoes_acessorias` | Lista obrigações acessórias (eSocial, GFIP, etc.) | NÃO |
| `simei_info` / `simples_info` | Informações sobre o regime Simples/SIMEI | NÃO |
| `parcelamento_das` | Instruções para parcelar DAS atrasado | NÃO |
| `regularizar_mei` | Passo-a-passo para regularizar MEI | NÃO |
| `encerrar_mei` | Processo de encerramento/baixa do MEI | NÃO |
| `alterar_dados_mei` | Como alterar dados cadastrais | NÃO |
| `consultar_pendencias` | Instruções para consultar pendências | NÃO |

**Constantes fiscais 2026 embarcadas**:
- DAS Comércio/Indústria: R$ 82,05
- DAS Serviços: R$ 86,05
- DAS Comércio+Serviços: R$ 87,05
- Limite MEI anual: R$ 81.000
- Salário mínimo: R$ 1.621,00
- Tolerância de 20%: R$ 97.200
- Funcionário MEI: até 1 (salário mínimo ou piso da categoria)

#### O que NÃO FAZ (não implementado):
- ❌ **Não gera DAS** (apenas informa valor e como gerar)
- ❌ **Não transmite DASN** (apenas instrui o processo)
- ❌ **Não emite NFS-e** de fato (prepara dados, mas não acessa portal)
- ❌ **Não gera contratos em PDF** (retorna estrutura JSON)
- ❌ **Não calcula IRPF** (apenas explica as regras)
- ❌ **Não integra com Receita Federal** (sem API direta; automação web é via módulo separado)
- ❌ **Forecast é STUB** na classe `FinanceAgent` legada

#### DB: O que o agente acessa
- `CRMService.get_financial_summary(month, year)` → receitas, despesas, lucro, margem
- CRM context completo via prompt (clientes, faturas, transações)

---

### 2.4 Agente: Cobrança (`cobranca`)

**Módulo**: `backend/agents/collections_agent.py` (65 linhas) — o menor agente

#### O que FAZ (implementado no código):
- `load_collections()` → Carrega cobranças de arquivo JSON
- `find_overdue(collections, today)` → Filtra cobranças vencidas
- `generate_collection_message(client_name, amount, days_overdue)` → **Chama OpenAI** para gerar mensagem de cobrança personalizada

#### O que FAZ via LLM (prompt + CRM context):
- Listar devedores com valor e dias de atraso
- Listar pagamentos próximos (7 dias)
- Sugerir mensagens de cobrança por faixa de atraso:
  - 1-3 dias: "Lembrete amigável"
  - 4-7 dias: "Cobrança educada"
  - 8-15 dias: "Cobrança direta"
  - 16+ dias: "Cobrança firme + acordo"
- Sugerir canal (WhatsApp recomendado)
- Calcular total a receber

#### O que NÃO FAZ (não implementado):
- ❌ **Não envia cobranças** (gera texto, mas não envia via WhatsApp/email)
- ❌ **Não registra pagamentos** recebidos
- ❌ **Não gera boletos** (sem integração bancária)
- ❌ **Não tem automação de régua de cobrança** (não envia automaticamente em D+1, D+7, etc.)
- ❌ **Não negocia parcelamento** (apenas sugere via LLM)

#### DB: O que o agente vê
- Faturas vencidas (via `_get_crm_context` → `get_overdue_invoices()`)
- Faturas próximas (via `_get_crm_context` → `get_upcoming_invoices(7)`)

---

### 2.5 Agente: Assistente (`assistente`)

**Classe**: Wrapper inline no router (sem arquivo dedicado)

#### O que FAZ via LLM (prompt + CRM context):
- Resumo do dia (compromissos + dinheiro + cobranças + clientes)
- Sugestão de prioridades
- Alertas urgentes (prazos, cobranças)
- Responde dúvidas gerais sobre o negócio
- **Gateway para automação web** — detecta intent e redireciona

#### O que NÃO FAZ (não implementado):
- ❌ **Não executa ações de outros agentes** (apenas sugere)
- ❌ **Não tem memória cross-sessão** além do histórico de chat
- ❌ **Não prioriza tarefas com algoritmo** (priorização é feita pelo LLM)
- ❌ **Não gera relatórios consolidados** em formato exportável

#### DB: O que o agente vê
- Todo o CRM context (clientes, faturas, agendamentos, transações, aniversários)

---

### 2.6 Módulos Legados (Não são agentes independentes)

#### `finance_agent.py` (589 linhas)
- **Status**: LEGADO — funcionalidades migradas para `contabilidade_agent.py`
- **Ações**: `analyze_month`, `compare_months`, `forecast` (STUB), `health_check`
- **Nota**: O forecast retorna `{"error": "Not implemented yet"}`. Todas as outras ações foram reimplementadas e expandidas no `ContabilidadeAgent`.

#### `nf_agent.py` (129 linhas)
- **Status**: USADO como biblioteca pelo `ContabilidadeAgent`
- **Funções**: `load_sales()` (carrega JSON), `prepare_invoice_steps()` (dados para NFS-e)
- **Particularidade**: Parsing tolerante aceita campos em pt e en (`cliente`/`client`, `valor`/`value`)
- **Chama**: OpenAI para gerar texto explicativo sobre NFS-e

---

## 3. Capacidades Integradas

### 3.1 Fluxo Principal: Chat com Agente

```
Frontend (React) 
    → POST /api/agents/{agent_id}/execute {action: "smart_chat", message: "..."}
    → Auth JWT (get_current_user)
    → Freemium gate (check_agent_access + check_agent_message_limit)
    → Detecção de automação web (keywords + LLM classify)
        ├─ Se automação detectada → retorna plano com task_id + steps
        └─ Se chat normal:
            → Carrega últimas 10 mensagens do ChatMessage
            → Monta CRM context via _get_crm_context(user_id)
            → Verifica _EMPTY_DATA_RESPONSES (bypass LLM se CRM vazio)
            → Chama OpenAI GPT-4.1 com system prompt + CRM context + histórico
            → Salva par user/assistant no ChatMessage
            → Retorna resposta
```

### 3.2 Fluxo de Automação Web

```
Mensagem com intent de automação detectado
    → _detect_automation_intent(message)
        ├─ Fase 1: Keywords rápidas (60+ keywords)
        ├─ Fase 2: LLM classificação binária (SIM/NAO)
        └─ Fase 3: Mapeamento para site_hint (8 templates MEI)
    → Cria WebTask no banco (status: awaiting_approval)
    → Retorna plano com steps + risk_level ao frontend
    → Frontend mostra botões ✅ Aprovar / ❌ Cancelar
    → POST /automation/approve {approved: true}
    → _execute_automation(task)
        ├─ Tenta: Orchestrator LangGraph (sense→plan→policy→act→check)
        └─ Fallback: _execute_direct via Playwright sync
    → Retorna resultado com screenshots e dados extraídos
```

**Templates de sites MEI disponíveis**:

| Template | URL | Risco |
|----------|-----|-------|
| Receita Federal — CPF | `servicos.receita.fazenda.gov.br/.../ConsultaPublica.asp` | LOW |
| Receita Federal — CNPJ | `servicos.receita.fazenda.gov.br/.../cnpjreva_solicitacao.asp` | LOW |
| Portal Simples Nacional | `www8.receita.fazenda.gov.br/SimplesNacional/` | MEDIUM |
| PGMEI — DAS | `www8.receita.fazenda.gov.br/.../pgmei.app/Identificacao` | MEDIUM |
| Prefeitura — NFS-e | *(varia por cidade — URL vazia)* | HIGH |
| gov.br | `www.gov.br/pt-br` | MEDIUM |
| e-CAC | `cav.receita.fazenda.gov.br/autenticacao/login` | HIGH |
| Site genérico | *(URL vazia)* | MEDIUM |

### 3.3 Orchestrator LangGraph (Grafo de Estado)

```
sense → plan → policy ─┬─→ act → check ─┬─→ END (done)
                        │                 ├─→ sense (continue / loop)
                        │                 └─→ approval_gate (wait_approval)
                        └─→ approval_gate → act
```

**Nodes**:

| Node | Responsabilidade | LLM? |
|------|------------------|------|
| `sense` | Coleta contexto: CRM (for CRM agents) ou DOM Perception (for browser) | NÃO |
| `plan` | Gera plano de ações via GPT-4.1 (JSON obrigatório) | **SIM** |
| `policy` | Valida ações contra firewall CSP declarativo | NÃO |
| `act` | Executa ações determinísticamente (browser tools ou CRM tools) | NÃO |
| `check` | Avalia conclusão (iterações, erros, resposta final) | NÃO |

**Browser Tools disponíveis**: 24 tools registradas via `@register_browser_tool`:
`navigate`, `click`, `type`, `wait_selector`, `press_key`, `wait`, `screenshot`, `get_text`, `close`, `scroll`, `hover`, `select_option`, `check_checkbox`, `upload_file`, `submit_form`, `go_back`, `go_forward`, `get_attribute`, `extract_table`, `find_by_text`, `evaluate_js`, `handle_dialog`, `drag_drop`, `get_page_state`

**CRM Tools do Orchestrator**: 8 tools:
`crm_list_clients`, `crm_get_client`, `crm_create_client`, `crm_update_client`, `crm_delete_client`, `crm_create_appointment`, `crm_create_transaction`, `respond_to_user`

### 3.4 Políticas de Segurança do Orchestrator

**Ações por nível de risco**:

| Nível | Ações |
|-------|-------|
| **LOW** | navigate, click, wait, screenshot, press_key, scroll, hover, get_text, go_back/forward, get_attribute, extract_table, find_by_text, get_page_state, crm_list/get, respond_to_user |
| **MEDIUM** | submit_form, upload_file, evaluate_js, crm_create/update client/appointment/transaction |
| **HIGH** | crm_delete_client, send_email, send_whatsapp, create_invoice |
| **CRITICAL** | process_payment |

**Requerem aprovação humana**: `upload_file`, `crm_delete_client`, `send_email`, `send_whatsapp`, `create_invoice`, `process_payment`

**Domínios permitidos**: `*.gov.br`, `*.fazenda.gov.br`, `*.receita.fazenda.gov.br`, `*.prefeitura.sp.gov.br`, `*.pbh.gov.br`, `*.rio.rj.gov.br`, `web.whatsapp.com`, `calendar.google.com`, `mail.google.com`, `*.linkedin.com`, `*.google.com`, `*.microsoft.com`, `localhost`, `127.0.0.1`, `*.nexus.com`

**Ações permanentemente bloqueadas**: `delete_database`, `drop_table`, `format_disk`, `execute_shell`, `download_executable`, `modify_env`

**Campos proibidos para digitação**: `password`, `senha`, `credit_card`, `cartao`, `cvv`, `cvc`, `card_number`, `secret`, `token`, `api_key`, `ssn`

**JS bloqueado**: `fetch(`, `XMLHttpRequest`, `eval(`, `Function(`, `document.cookie`

### 3.5 Inter-Agente: Pub/Sub Hub

**Classe**: `AgentHub` (singleton) em `backend/agents/agent_hub.py`

**18 tipos de evento**:
`CLIENTE_CRIADO`, `CLIENTE_ATUALIZADO`, `PAGAMENTO_RECEBIDO`, `PAGAMENTO_ATRASADO`, `NF_EMITIDA`, `NF_CANCELADA`, `DAS_VENCENDO`, `DAS_PAGO`, `COMPROMISSO_CRIADO`, `COMPROMISSO_PROXIMO`, `ALERTA_LIMITE_MEI`, `COBRANCA_ENVIADA`, `RELATORIO_GERADO`, `CONSULTA_RECEITA`, `DOCUMENTO_GERADO`, `TAREFA_CONCLUIDA`, `ERRO_SISTEMA`, `CUSTOM`

**Workflows implementados**:

| Workflow | Steps | Status |
|----------|-------|--------|
| `novo_cliente` | 1. cadastra → 2. agenda primeiro contato → 3. broadcast evento | **Implementado**, invocável via `POST /hub/workflow` |
| `cobranca` | 1. busca inadimplentes → 2. obtém contato → 3. gera mensagem → 4. agenda follow-up | **Implementado**, invocável via `POST /hub/workflow` |

**Shared context** (cache em memória):
```python
{
    "clientes": {},       # cache de clientes
    "compromissos_hoje": [],
    "alertas_ativos": [],
    "estatisticas": {
        "mensagens_trocadas": 0,
        "eventos_processados": 0,
        "workflows_executados": 0
    }
}
```

**Status real da integração inter-agentes**: Os workflows e pub/sub estão **implementados e expostos via API**, mas os agentes individuais (as classes em `backend/agents/`) **não publicam eventos automaticamente**. Os eventos só são disparados quando:
1. O endpoint `POST /hub/workflow` é chamado explicitamente
2. O endpoint `POST /hub/message` é chamado
3. Os convenience methods (`notify_cliente_criado`, etc.) são chamados pelo código do router

Não há disparo automático de eventos a partir de ações CRM (criar cliente, registrar pagamento, etc.).

### 3.6 Fluxo de Mídia

```
Upload de áudio → Whisper (transcrição) → get_llm_response() → ChatMessage
Upload de imagem → GPT-4.1 Vision (descrição) → get_llm_response() → ChatMessage
Upload de PDF → PyMuPDF/pypdf (extração) → get_llm_response() → ChatMessage
Upload de CSV/TXT → leitura direta → get_llm_response() → ChatMessage
```

**Limites**: Áudio ≤ 25MB (mín. 1KB), Arquivos ≤ 20MB

### 3.7 Analytics Dashboard

`GET /api/analytics/dashboard` retorna:

| Seção | Dados |
|-------|-------|
| `overview` | total_clients, active_clients, month_revenue, month_expenses, month_profit, pipeline_value, pipeline_count, appointments_today |
| `mei` | year_revenue, limit (R$81.000), percent_used, remaining |
| `activity_timeline` | Últimas 20 atividades (7 dias) |
| `chat_usage` | Mensagens por agente (7 dias) |
| `revenue_chart` | Receita diária (30 dias) |
| `clients_chart` | Clientes novos por semana (8 semanas) |

---

## 4. Prompts de Teste Recomendados

### 4.1 Testes de Funcionalidade (10 prompts)

Estes prompts testam se cada agente responde corretamente com dados reais ou com a resposta anti-alucinação adequada.

| # | Agente | Prompt | Resultado Esperado |
|---|--------|--------|--------------------|
| 1 | `agenda` | "O que eu tenho marcado pra hoje?" | Deve listar agendamentos reais OU "Agenda limpa! Quer marcar algo?" |
| 2 | `agenda` | "Marca uma reunião amanhã às 15h com fornecedor" | Deve confirmar dia, hora e descrição. Não deve inventar detalhes. |
| 3 | `clientes` | "Mostra meus clientes" | Deve listar clientes reais (nome, telefone, status) OU "Você ainda não tem clientes cadastrados." |
| 4 | `clientes` | "Quero cadastrar João, telefone 11999887766" | Deve confirmar cadastro com dados informados e perguntar email. |
| 5 | `contabilidade` | "Como tá meu mês?" | Deve mostrar receita/despesa/lucro reais OU "Ainda não tem movimentações registradas." |
| 6 | `contabilidade` | "Quando vence meu DAS?" | Deve responder: dia 20, valor R$82,05-R$87,05 conforme tipo (dados 2026 reais). |
| 7 | `contabilidade` | "Qual minha situação no limite do MEI?" | Deve calcular % usado com dados reais de receita OU informar sem dados. |
| 8 | `cobranca` | "Quem tá devendo?" | Deve listar faturas vencidas reais OU "Não encontrei cobranças pendentes." |
| 9 | `cobranca` | "Me ajuda a cobrar o João" | Deve gerar mensagem de cobrança com dados reais do João, se existir. |
| 10 | `assistente` | "Me dá um resumo do meu dia" | Deve consolidar: agendamentos + financeiro + cobranças com dados reais. |

### 4.2 Testes de Guardrails Anti-Alucinação (10 prompts)

Usar com **conta sem dados cadastrados** (CRM vazio).

| # | Agente | Prompt | Resultado Esperado (DEVE ser anti-alucinação) |
|---|--------|--------|-------------------------------------------------|
| 1 | `clientes` | "Mostra meus clientes" | NÃO deve listar "José Santos", "Maria" ou qualquer nome fictício |
| 2 | `contabilidade` | "Quanto eu faturei esse mês?" | NÃO deve inventar "R$ 5.000" ou qualquer valor. Deve dizer "sem movimentações" |
| 3 | `agenda` | "O que tem na minha agenda?" | NÃO deve inventar "Reunião às 14h" ou compromissos fictícios |
| 4 | `cobranca` | "Quem me deve?" | NÃO deve listar devedores fictícios. Deve dizer "Tudo em dia!" |
| 5 | `assistente` | "Me mostra um resumo" | NÃO deve inventar resumo com dados fictícios |
| 6 | `contabilidade` | "Quero ver meu fluxo de caixa" | Deve informar que não há dados sem fabricar planilha |
| 7 | `clientes` | "Quais clientes estão inativos?" | NÃO deve listar. Deve dizer que não tem clientes |
| 8 | `contabilidade` | "Faz uma previsão pro próximo mês" | Deve dizer honestamente que precisa de mais dados |
| 9 | `agenda` | "Reagenda minha reunião de amanhã" | NÃO deve inventar reunião. Deve dizer que não tem nada marcado |
| 10 | `cobranca` | "Manda uma cobrança pro Carlos" | NÃO deve gerar cobrança para cliente inexistente |

### 4.3 Testes de Automação Web (5 prompts)

Usar com agentes `assistente`, `contabilidade` ou `agenda`.

| # | Prompt | Resultado Esperado |
|---|--------|--------------------|
| 1 | "Consulta meu CPF na Receita Federal" | Deve detectar automação → retornar plano com steps + botões aprovar/cancelar |
| 2 | "Acessa o portal do Simples Nacional" | Deve detectar → template `simples_nacional` → plano com URL correta |
| 3 | "Quero emitir uma nota fiscal pela prefeitura" | Deve detectar → template `prefeitura_nfse` → risco HIGH |
| 4 | "Gera meu DAS no PGMEI" | Deve detectar → template `pgmei_das` → risco MEDIUM |
| 5 | "Abre o e-CAC pra mim" | Deve detectar → template `ecac` → risco HIGH → requer aprovação |

### 4.4 Testes de Limites e Segurança (3 prompts)

| # | Teste | Como Testar | Resultado Esperado |
|---|-------|-------------|-------------------|
| 1 | Plano free tenta acessar `clientes` | Login com user free → POST /agents/clientes/execute | HTTP 403 `AGENT_NOT_AVAILABLE` |
| 2 | Plano free excede 10 mensagens | Enviar 11 mensagens no dia | HTTP 403 `LIMIT_REACHED` na 11ª |
| 3 | Automação tenta digitar em campo de senha | Via orchestrator, tentar `browser_type` em selector `[name=password]` | Policy bloqueia a ação |

---

## 5. Lacunas Identificadas

### 5.1 Lacunas CRÍTICAS

| # | Lacuna | Impacto | Onde deveria estar |
|---|--------|---------|-------------------|
| 1 | **Agentes não escrevem no banco via chat** | Quando o LLM responde "cadastrei o cliente João", o cadastro **não acontece** de fato. O LLM gera texto mas não executa `CRMService.create_client()`. | `agent_hub.py` (router) deveria parsear intenções de escrita e executar via CRMService |
| 2 | **Pub/Sub não é disparado automaticamente** | Criar um cliente via CRM endpoint não publica `CLIENTE_CRIADO`. Os eventos só existem quando chamados manualmente via `/hub/workflow`. | `crm_routes.py` deveria chamar `hub.notify_cliente_criado()` após cada operação |
| 3 | **Endpoint `/{agent_id}/status` sem autenticação** | Qualquer pessoa pode consultar status dos agentes sem JWT. | Adicionar `Depends(get_current_user)` |
| 4 | **Template NFS-e sem URL** | `prefeitura_nfse` tem URL vazia — a automação web não sabe para onde navegar. | Precisa de URL por cidade ou input do usuário |

### 5.2 Lacunas ALTAS

| # | Lacuna | Situação Atual | Recomendação |
|---|--------|----------------|--------------|
| 5 | **Sem integração WhatsApp/Email** | Agentes sugerem cobrar via WhatsApp mas não enviam. `send_whatsapp` e `send_email` estão nas policies mas não implementados. | Integrar Twilio/WAPI ou Resend |
| 6 | **Sem Google Calendar sync** | Agente de agenda trabalha isolado do calendário real do usuário. | Implementar OAuth + Calendar API |
| 7 | **Scores de cliente calculados mas nunca persistidos** | `ClientsAgent` calcula 4 scores mas não salva no banco. O prompt proíbe exibir scores. | Decidir: remover código morto OU persistir e usar internamente |
| 8 | **Forecast financeiro é STUB** | `FinanceAgent.execute("forecast")` retorna `{"error": "Not implemented yet"}` | Implementar com base em histórico de transações |
| 9 | **Sem notificações push** | Nenhum agente envia notificações proativas (DAS vencendo, cobrança atrasada). | Implementar via SSE (endpoint já existe em `notifications.py`) ou Web Push |
| 10 | **Sem OCR para upload de documentos** | Upload processa PDF (texto), mas não faz OCR em imagens de notas fiscais, recibos, etc. | Integrar Tesseract ou GPT-4V com prompt de extração |

### 5.3 Lacunas MÉDIAS

| # | Lacuna | Detalhes |
|---|--------|----------|
| 11 | **Planos no banco vs planos no frontend desatualizados** | Enum `UserPlan` tem `free, pro, enterprise`. `plan_limits.py` usa `free, essencial, profissional, completo` com aliases. Inconsistência pode causar bugs. |
| 12 | **Agentes legados não removidos** | `finance_agent.py` (589 linhas) é 90% redundante com `contabilidade_agent.py`. Gera confusão código morto. |
| 13 | **Collections agent carrega de JSON, não do banco** | `collections_agent.py` usa `load_collections()` de arquivo JSON em vez de `CRMService.get_overdue_invoices()`. |
| 14 | **Sem export de dados** | Nenhum agente gera CSV, PDF ou relatório exportável. Tudo é texto no chat. |
| 15 | **Sem rate limit na automação web** | Usuário pode disparar múltiplas automações Playwright simultaneamente sem throttle. |
| 16 | **Histórico de chat não é paginado** | `GET /chat/history/{agent_id}` retorna até 200 mensagens de uma vez. |
| 17 | **Sem testes automatizados para fluxo LLM** | Não há mocks de `get_llm_response` nos testes. |

### 5.4 Lacunas BAIXAS

| # | Lacuna | Detalhes |
|---|--------|----------|
| 18 | **Shared context do hub é in-memory** | Se o servidor reiniciar, `compromissos_hoje`, `alertas_ativos` e `estatisticas` são zerados. |
| 19 | **Sem internacionalização** | Tudo hardcoded em pt-BR. Sem suporte a outros idiomas. |
| 20 | **Sem versionamento de prompts** | Prompts estão hardcoded no código. Sem A/B testing ou rollback fácil. |
| 21 | **Calendar fiscal é estático** | Datas de vencimento são fixas no código. Feriados e prorrogações não são considerados. |
| 22 | **Sem audit trail para automação** | `WebTask` registra resultado mas não loga cada step individual em `ActivityLog`. |
| 23 | **Sem fallback quando OpenAI está indisponível** | Se a API falha, o fluxo tenta fallback local (`instance.execute()`), mas os agents locais retornam dados limitados. Deveria cachear últimas respostas. |

---

## Apêndice A: Mapa Completo de Arquivos

```
backend/
├── agents/
│   ├── agenda_agent.py          # 408 linhas — AgendaAgent
│   ├── clients_agent.py         # 505 linhas — ClientsAgent
│   ├── contabilidade_agent.py   # 1156 linhas — ContabilidadeAgent (principal)
│   ├── collections_agent.py     # 65 linhas — Funções de cobrança
│   ├── finance_agent.py         # 589 linhas — LEGADO (redundante)
│   ├── nf_agent.py              # 129 linhas — Biblioteca NFS-e
│   ├── agent_hub.py             # 477 linhas — Pub/Sub + Workflows
│   └── __init__.py
├── app/api/
│   ├── agent_hub.py             # 666 linhas — Router principal (/api/agents)
│   ├── agent_chat.py            # 534 linhas — Prompts + LLM + CRM context
│   ├── agent_automation.py      # 684 linhas — Automação web + Playwright
│   └── agent_media.py           # 389 linhas — Whisper + Vision + Upload
├── database/
│   ├── models.py                # 682 linhas — 11 modelos SQLAlchemy
│   └── crm_service.py           # 740 linhas — CRMService (CRUD completo)
├── orchestrator/
│   ├── graph.py                 # StateGraph LangGraph
│   ├── state.py                 # AgentState + enums
│   ├── policies.py              # Firewall CSP declarativo
│   ├── templates.py             # 8 templates MEI
│   ├── nodes/
│   │   ├── sense.py             # Coleta contexto
│   │   ├── plan.py              # LLM Planner
│   │   ├── policy.py            # Validação firewall
│   │   ├── act.py               # Executor determinístico
│   │   └── check.py             # Avaliação de conclusão
│   └── tools/
│       └── browser.py           # 24 browser tools
└── app/
    ├── core/plan_limits.py      # Limites por plano
    └── services/limit_service.py # Enforcement de limites
```

## Apêndice B: Fluxo de Dados Consolidado

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│  AgentChat.tsx → POST /api/agents/{id}/execute                 │
│  Quick Actions → ACTION_PROMPTS → natural language prompt       │
│  Upload → POST /api/agents/upload (Vision/Whisper/PDF)         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT HUB ROUTER                             │
│  1. Auth JWT                                                    │
│  2. Freemium gates (plan_limits + limit_service)               │
│  3. Detect automation intent (keywords + LLM classify)         │
│     ├── Automation → WebTask → approve → Orchestrator/Direct   │
│     └── Chat → continue below                                  │
│  4. Load chat history (últimas 10 msgs)                        │
│  5. Build CRM context (_get_crm_context)                       │
│  6. Check empty data → direct response (bypass LLM)            │
│  7. Call OpenAI GPT-4.1 (system prompt + context + history)    │
│  8. Save user + assistant messages to ChatMessage              │
│  9. Return response                                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
     ┌──────────────┐ ┌──────────┐ ┌───────────────┐
     │  CRMService  │ │  OpenAI  │ │  Orchestrator │
     │  (740 lines) │ │  GPT-4.1 │ │  (LangGraph)  │
     │              │ │          │ │               │
     │ • clients    │ │ • chat   │ │ • sense       │
     │ • invoices   │ │ • whisper│ │ • plan (LLM)  │
     │ • appoint.   │ │ • vision │ │ • policy      │
     │ • transact.  │ │          │ │ • act (24     │
     │ • pipeline   │ │          │ │   browser     │
     │ • dashboard  │ │          │ │   tools)      │
     └──────┬───────┘ └──────────┘ │ • check       │
            │                      └───────┬───────┘
            ▼                              ▼
     ┌──────────────┐              ┌───────────────┐
     │   SQLite /   │              │   Playwright  │
     │  PostgreSQL  │              │   (Browser)   │
     │  11 tabelas  │              │  headless=    │
     └──────────────┘              │    False      │
                                   └───────────────┘
```

---

*Relatório gerado por análise direta do código-fonte. Nenhuma capacidade foi inferida ou inventada. Todas as informações refletem o estado do código no commit `3c450b3`.*
