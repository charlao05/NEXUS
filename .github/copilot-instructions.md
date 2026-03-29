# Copilot Instructions for NEXUS

## Visão Geral

NEXUS é uma plataforma de diagnóstico empresarial e automação com agentes IA, voltada para MEIs e pequenas empresas. Stack: FastAPI + React 18 + TypeScript + Vite + OpenAI GPT + SQLite/PostgreSQL + Stripe + Playwright.

---

## MCP Servers Disponíveis

O projeto expõe 3 servidores MCP via `.vscode/mcp.json`. Em Agent Mode, use **Configure Tools** para ativá-los.

### 1. `nexus-dev` — Tools Internas do Projeto

Servidor customizado em `mcp_server.py` (stdio, FastMCP). Executa com `.venv/Scripts/python.exe`.

| Tool | Descrição | Exemplo de uso |
|------|-----------|----------------|
| `health_check()` | GET /health — verifica backend, DB, Redis | "Verifique se o backend está online" |
| `run_tests(filter, verbose)` | pytest com filtros (-k) | "Rode os testes de auth" |
| `lint_backend(fix)` | Ruff linter no Python | "Lint com --fix no backend" |
| `typecheck_frontend()` | tsc --noEmit | "Verifique erros TypeScript" |
| `db_stats()` | Contagem de users/clients/invoices (readonly) | "Quantos usuários temos?" |
| `db_query(sql)` | SQL readonly (SELECT only, 50 rows max) | "Liste os últimos 5 usuários" |
| `tail_logs(lines)` | Últimas N linhas de logs/automation.log | "Mostre os logs recentes" |
| `list_agents()` | Lista os 7 agentes IA | "Quais agentes existem?" |
| `list_routes()` | Todas as rotas da API (via /openapi.json) | "Liste os endpoints" |
| `project_overview()` | Mapa completo do projeto | "Visão geral do NEXUS" |
| `test_login(email, password)` | Testa POST /api/auth/login | "Teste login do admin" |
| `frontend_lint()` | ESLint no frontend | "Rode ESLint" |

**Resources (contexto estático):**
- `nexus://env-config` — Chaves do .env (valores mascarados)
- `nexus://db-schema` — Schema SQLite completo (CREATE TABLE statements)

### 2. `context7` — Documentação Atualizada de Libs

Quando o prompt incluir "use context7", injeta docs oficiais e versionadas (React 19, FastAPI, Tailwind 4, etc.) no contexto, evitando APIs desatualizadas ou hallucinations.

### 3. `playwright` — Browser Automation

Permite ao agente controlar o browser: abrir URLs, clicar, digitar, screenshot, validar UI.

---

## Backend — FastAPI

- **Entry point**: `backend/main.py` → `app = FastAPI(title="NEXUS API", version="1.0.0")`
- **Porta**: 8000 (dev), `$PORT` (prod/Render)
- **Modelo IA**: `gpt-4.1` via env `OPENAI_MODEL`
- **Comando dev**: `python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000`
- **Ambiente**: `.venv/Scripts/python.exe` (Windows)

### Routers Montados

| Prefix | Tags | Arquivo |
|--------|------|---------|
| `/api/auth` | authentication | `backend/app/api/auth.py` (1262 linhas) |
| `/api/agents` | agents | `backend/app/api/agent_hub.py` |
| `/api/agents` | agents-media | `backend/app/api/agent_media.py` |
| `/api/crm` | crm | `backend/app/api/crm_routes.py` |
| `/api/chat` | chat-history | `backend/app/api/chat_history.py` |
| `/api/analytics` | analytics | `backend/app/api/chat_history.py` |
| `/api/notifications` | notifications | `backend/app/api/notifications.py` (SSE) |
| `/api/admin` | admin | `backend/app/api/admin.py` |
| `/api/orchestrator` | Orchestrator | `backend/app/api/orchestrator.py` (LangGraph) |
| `/api/agents/automation` | Agent Automation | `backend/app/api/agent_automation.py` |
| `/api/telegram` | telegram | `backend/app/api/telegram.py` (webhook do bot) |

### Endpoints Diretos
- `GET /health` — status de DB, Redis, Sentry
- `GET /` — `{"message": "NEXUS API está rodando"}`
- `GET /docs` — Swagger (apenas dev)

### Middleware
1. **CORS** — origens via `CORS_ORIGINS` env; dev adiciona localhost:5173/5175
2. **SecurityHeaders** — nosniff, DENY, XSS, HSTS (prod), CSP (prod)
3. **RateLimit** — por plano, Redis sorted sets ou in-memory fallback

---

## Agentes IA

7 agentes em `backend/agents/`:

| Agente | Responsabilidade |
|--------|------------------|
| `agenda_agent.py` | Prazos fiscais, NFs, reuniões, lembretes, multi-canal |
| `agent_hub.py` | Orquestração inter-agentes, broadcast de eventos, cache |
| `clients_agent.py` | CRM — cadastro, histórico, scores IA, segmentação, tags |
| `collections_agent.py` | Cobranças overdue, notificações |
| `contabilidade_agent.py` | Contabilidade MEI — 15 obrigações (DAS, DASN, NFS-e, eSocial) |
| `finance_agent.py` | Análise financeira MEI — lucro, alertas DAS, comparações |
| `nf_agent.py` | Nota Fiscal — geração de steps, campos obrigatórios |

Enum de agentes: `AGENDA, CLIENTES, FINANCEIRO, COBRANCA, DOCUMENTOS, ASSISTENTE`

---

## Frontend — React + Vite

- **Dev**: `cd frontend && npm install && npm run dev` (porta 5173)
- **Proxy**: `/api` → `http://127.0.0.1:8000` (vite.config.ts)
- **Build**: `tsc && vite build` → `dist/`

### Rotas Principais
| Rota | Componente | Auth |
|------|------------|------|
| `/`, `/login` | NexusCodexLogin | Não |
| `/dashboard` | Dashboard | Sim (plano válido) |
| `/agents` | Agents | Sim |
| `/agents/:id` | AgentConfig | Sim |
| `/admin` | AdminDashboard | Sim (admin) |
| `/pricing` | Pricing | Sim |
| `/onboarding` | Onboarding | Sim (pendente) |
| `/docs/:section` | Docs | Sim |
| `/diag` | DiagLogin | Não (diagnóstico) |
| `/termos`, `/privacidade` | Legal | Não |

### Planos válidos
`free`, `essencial`, `profissional`, `completo`, `pro`, `enterprise`

### Contextos React
- `AuthContext` — auth state, login/logout, token management
- `ThemeContext` — dark/light mode

---

## Database

- **Dev**: SQLite em `backend/test.db` (path absoluto no .env: `DATABASE_URL=sqlite:///C:/Users/Charles/Desktop/NEXUS/backend/test.db`)
- **Prod**: PostgreSQL via `DATABASE_URL` no Render
- **Auto-migrate**: `_auto_migrate_columns()` para SQLite — adiciona colunas faltantes automaticamente

### Modelos (SQLAlchemy)

| Modelo | Tabela | Uso |
|--------|--------|-----|
| `User` | users | Auth, plano, role, OAuth, Stripe, LGPD |
| `Subscription` | subscriptions | Stripe subscriptions |
| `Client` | clients | CRM — dados, segmentação, scores IA |
| `Interaction` | interactions | Histórico com cliente |
| `Opportunity` | opportunities | Pipeline de vendas |
| `Appointment` | appointments | Agendamentos |
| `Transaction` | transactions | Receitas e despesas |
| `Invoice` | invoices | Faturas |
| `ChatMessage` | chat_messages | Chat por user/agent |
| `ActivityLog` | activity_logs | Timeline de atividades |
| `WebTask` | web_tasks | Automação web (human-in-the-loop) |

### Enums
- `UserPlan`: free, pro, enterprise
- `UserStatus`: active, suspended, deleted
- `ClientSegment`: lead, prospect, standard, premium, vip, churned
- `OpportunityStage`: prospeccao → qualificacao → proposta → negociacao → fechamento → ganho/perdido
- `TaskStatus`: pending → approved → running → completed/failed/cancelled

---

## Orchestrator (LangGraph)

Em `backend/orchestrator/`:
- **StateGraph**: sense → plan → policy → (wait_approval?) → act → check → END
- **Risk levels**: LOW, MEDIUM, HIGH, CRITICAL
- **Human-in-the-loop**: `interrupt_before` para ações de risco
- **Nodes**: act.py, check.py, plan.py, policy.py, sense.py
- **Browser tool**: Playwright via `browser.py`

---

## Variáveis de Ambiente Principais

```
# Core
JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES
DATABASE_URL                    # sqlite:/// (dev) ou postgresql:// (prod)
OPENAI_API_KEY, OPENAI_MODEL   # gpt-4.1
ENVIRONMENT                     # development | production | test
LOG_LEVEL                       # INFO

# Payments
STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET

# OAuth
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
FACEBOOK_CLIENT_ID, FACEBOOK_CLIENT_SECRET

# Frontend
VITE_API_URL                    # NÃO definir em dev (usar proxy do Vite)
VITE_GOOGLE_CLIENT_ID

# Services
REDIS_URL, SENTRY_DSN, RESEND_API_KEY, EMAIL_FROM
CORS_ORIGINS, FRONTEND_URL, BACKEND_BASE_URL

# Telegram Bot
TELEGRAM_BOT_TOKEN              # Token do @BotFather
TELEGRAM_BOT_USERNAME            # Username do bot (sem @)
TELEGRAM_WEBHOOK_SECRET          # Secret para validar webhook
TELEGRAM_ADMIN_CHAT_ID           # Chat ID do admin para alertas
```

**IMPORTANTE**: Em dev, `VITE_API_URL` deve estar COMENTADO no `frontend/.env.local` — caso contrário, bypass do proxy Vite causa CORS.

---

## Testes

```bash
# Backend (pytest)
cd NEXUS && .venv/Scripts/python.exe -m pytest tests/ -v --tb=short

# Filtrar testes
pytest -k "test_auth"
pytest -k "test_freemium"

# Frontend
cd frontend && npm run lint
cd frontend && npx tsc --noEmit

# E2E (Docker)
docker compose --profile test up --build
```

**pytest.ini**: testpaths = `backend/tests`, `e2e/tests`, `tests`

---

## Deploy (Render)

- **Backend**: Python 3.12, uvicorn, health check `/health`
- **Frontend**: Static site (Vite build), SPA rewrite `/* → /index.html`
- Config em `render.yaml`

---

## Docker Compose

- **postgres**: PostgreSQL 16 Alpine (porta 5432)
- **redis**: Redis 7 Alpine (porta 6379, AOF, 128mb LRU)
- **backend**: FastAPI (porta 8000)
- **frontend**: Nginx (porta 80)
- **e2e**: Profile `test`

---

## Convenções de Código

- **Nomes em português** em CLI, agentes e mensagens ao usuário
- **Aceitar pt/en** para nomes de campos (parsing tolerante nos agentes)
- JSON com `ensure_ascii=False` para conteúdo user-facing
- Logging via `logging_utils.get_logger`
- Backend: exception handler global retorna 500 genérico + Sentry
- Rate limiting por plano (free < pro < enterprise)
- Queue operations devem ser O(log n)
- Senhas/segredos NUNCA em código ou logs
- Ações destrutivas requerem aprovação explícita
- Registrar resultados em `logs/automation.log`

---

## Comandos de Inicialização Rápida

```powershell
# Backend
Push-Location "C:\Users\Charles\Desktop\NEXUS"
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (novo terminal)
Push-Location "C:\Users\Charles\Desktop\NEXUS\frontend"
npm run dev -- --host 127.0.0.1 --port 5173

# Ou usar o batch
.\INICIAR_NEXUS.bat
```

---

## Credenciais de Teste (Dev)

- **Admin**: `appnexxus.app@gmail.com` / `Admin@123` (id=57, plan=pro, role=admin)
- **Health**: `GET http://127.0.0.1:8000/health`
- **Diagnostico**: `http://localhost:5173/diag`

---

## Estrutura de Diretórios

```
NEXUS/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── agents/              # 7 agentes IA
│   ├── app/api/             # 14 routers/services
│   ├── database/            # models.py, crm_service.py
│   ├── orchestrator/        # LangGraph state machine
│   ├── services/            # llm_service, web_automation
│   ├── browser/             # Playwright actions
│   └── tests/               # pytest suites
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Routes
│   │   ├── pages/           # 14 pages
│   │   ├── components/      # 5 components
│   │   └── contexts/        # Auth, Theme
│   └── vite.config.ts       # Proxy /api → :8000
├── mcp_server.py            # MCP server (14 tools + 2 resources)
├── .vscode/mcp.json         # 3 MCP servers config
├── config/                  # sites.yaml, service accounts
├── data/                    # Sample datasets
├── scripts/                 # Utility scripts
├── logs/                    # automation.log
├── e2e/                     # E2E tests
├── render.yaml              # Render deploy config
├── docker-compose.yml       # Dev containers
└── .env                     # Environment variables
```
