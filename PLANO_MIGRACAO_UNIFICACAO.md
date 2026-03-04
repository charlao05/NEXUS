# 🔄 PLANO DE MIGRAÇÃO: CODEX → NEXUS UNIFICADO

**Data de Início:** 4 de Janeiro de 2026  
**Estratégia:** Opção B - Unificação Completa  
**Meta:** MVP em 4-5 dias  
**Status:** 🟢 EM EXECUÇÃO

---

## 🎯 OBJETIVO

Unificar **CODEX-OPERATOR** (backend + agentes) com **NEXUS** (frontend) em uma única plataforma com:
- ✅ Marca única: **NEXUS**
- ✅ UX consistente
- ✅ Arquitetura monorepo
- ✅ Deploy simplificado
- ✅ Manutenção centralizada

---

## 📊 ESTRUTURA FINAL (NEXUS Unificado)

```
NEXUS/
├── 📱 frontend/                    # React + Vite
│   ├── src/
│   │   ├── components/            # UI components
│   │   ├── pages/                 # Páginas principais
│   │   ├── services/              # API clients
│   │   │   ├── api.ts             # Axios setup
│   │   │   ├── agentService.ts    # Agentes
│   │   │   ├── paymentService.ts  # Stripe
│   │   │   └── diagnosticService.ts
│   │   ├── hooks/                 # React hooks
│   │   └── utils/                 # Utilities
│   ├── vite.config.ts
│   ├── package.json
│   └── .env.local
│
├── ⚙️ backend/                     # FastAPI (migrado do CODEX)
│   ├── main.py                    # App principal
│   ├── app/
│   │   ├── api/                   # Routers
│   │   │   ├── payments.py        # Stripe
│   │   │   ├── adsense.py         # AdSense
│   │   │   ├── agents.py          # 🆕 Agentes
│   │   │   ├── diagnostics.py     # 🆕 Diagnósticos
│   │   │   ├── queue.py           # 🆕 Filas
│   │   │   └── auth.py            # 🆕 Clerk
│   │   ├── models/                # Database models
│   │   ├── services/              # Business logic
│   │   └── utils/                 # Utilities
│   ├── agents/                    # 🆕 Agentes de IA
│   │   ├── site_agent.py
│   │   ├── deadlines_agent.py
│   │   ├── attendance_agent.py
│   │   ├── finance_agent.py
│   │   ├── nf_agent.py
│   │   └── collections_agent.py
│   ├── workflows/                 # 🆕 Workflows
│   │   ├── instagram_lead_express.py
│   │   ├── lead_qualificacao.py
│   │   └── ...
│   ├── integrations/              # 🆕 Integrações externas
│   │   ├── whatsapp_api.py
│   │   ├── telegram_api.py
│   │   ├── gmail_api.py
│   │   └── google_calendar.py
│   ├── core/                      # 🆕 Core systems
│   │   ├── agent_queue.py
│   │   └── llm_client.py
│   ├── browser/                   # 🆕 Playwright
│   │   ├── playwright_client.py
│   │   └── actions.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env
│
├── 🗄️ data/                       # Dados e configs
│   ├── mei_obligations.json
│   ├── mei_schedule.json
│   └── ...
│
├── 📋 config/                     # Configurações
│   ├── sites.yaml
│   └── sites/
│
├── 🧪 tests/                      # Testes unificados
│   ├── frontend/
│   └── backend/
│
├── 📜 scripts/                    # Deploy scripts
│   ├── deploy.ps1
│   └── setup_env.ps1
│
├── 📚 docs/                       # Documentação
│   ├── API.md
│   ├── AGENTS.md
│   └── DEPLOYMENT.md
│
├── 🌐 Landing/                    # Landing page
│   └── index.html
│
├── 📄 Root files
│   ├── README.md                  # 🆕 Novo README unificado
│   ├── ARCHITECTURE.md            # 🆕 Arquitetura
│   ├── docker-compose.yml         # 🆕 Local development
│   ├── .gitignore
│   └── package.json               # 🆕 Monorepo scripts
```

---

## 🔄 FASES DA MIGRAÇÃO

### **FASE 1: Preparação (30 min) - DIA 1**

#### 1.1 Criar estrutura de pastas NEXUS
```powershell
cd C:\Users\Charles\Desktop\NEXUS
New-Item -ItemType Directory -Force -Path backend, backend\app, backend\app\api
New-Item -ItemType Directory -Force -Path backend\agents, backend\workflows
New-Item -ItemType Directory -Force -Path backend\integrations, backend\core
New-Item -ItemType Directory -Force -Path backend\browser, backend\app\models
New-Item -ItemType Directory -Force -Path data, config, tests, scripts, docs
```

#### 1.2 Backup do estado atual
```powershell
# Criar backup de ambos os projetos
Copy-Item -Recurse C:\Users\Charles\Desktop\NEXUS C:\Users\Charles\Desktop\NEXUS_BACKUP_04JAN
Copy-Item -Recurse C:\Users\Charles\Desktop\codex-operator C:\Users\Charles\Desktop\CODEX_BACKUP_04JAN
```

---

### **FASE 2: Migração do Backend (2h) - DIA 1**

#### 2.1 Copiar Backend Core
```powershell
$source = "C:\Users\Charles\Desktop\codex-operator\backend"
$dest = "C:\Users\Charles\Desktop\NEXUS\backend"

# Copiar arquivos principais
Copy-Item "$source\main.py" "$dest\"
Copy-Item "$source\requirements.txt" "$dest\"
Copy-Item -Recurse "$source\app" "$dest\" -Force
```

#### 2.2 Copiar Agentes
```powershell
$source = "C:\Users\Charles\Desktop\codex-operator\src"
$dest = "C:\Users\Charles\Desktop\NEXUS\backend"

Copy-Item -Recurse "$source\agents" "$dest\" -Force
Copy-Item -Recurse "$source\workflows" "$dest\" -Force
Copy-Item -Recurse "$source\integrations" "$dest\" -Force
Copy-Item -Recurse "$source\core" "$dest\" -Force
Copy-Item -Recurse "$source\browser" "$dest\" -Force
Copy-Item -Recurse "$source\utils" "$dest\" -Force
```

#### 2.3 Copiar Dados e Configs
```powershell
Copy-Item -Recurse "C:\Users\Charles\Desktop\codex-operator\data" "C:\Users\Charles\Desktop\NEXUS\" -Force
Copy-Item -Recurse "C:\Users\Charles\Desktop\codex-operator\config" "C:\Users\Charles\Desktop\NEXUS\" -Force
```

---

### **FASE 3: Ajustar Imports (1h) - DIA 1**

#### 3.1 Atualizar imports nos agentes
```python
# ANTES (CODEX):
from src.utils import llm_client
from src.browser import playwright_client

# DEPOIS (NEXUS):
from backend.utils import llm_client
from backend.browser import playwright_client
```

#### 3.2 Atualizar paths em configs
```python
# backend/main.py
import sys
from pathlib import Path

# Adicionar backend ao path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
```

---

### **FASE 4: Criar APIs REST para Agentes (6h) - DIA 2**

#### 4.1 Criar `backend/app/api/agents.py`
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from backend.agents import site_agent

router = APIRouter(prefix="/api/agents", tags=["agents"])

class SiteAutomationRequest(BaseModel):
    site: str
    objetivo: str
    dry_run: bool = False

@router.post("/site-automation")
async def site_automation(request: SiteAutomationRequest):
    try:
        plano = site_agent.planejar(request.site, request.objetivo)
        if not request.dry_run:
            site_agent.executar_plano(request.site, plano)
        return {"status": "success", "plano": plano}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 4.2 Criar `backend/app/api/diagnostics.py`
```python
from fastapi import APIRouter
from pydantic import BaseModel
from openai import OpenAI

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])

class DiagnosticRequest(BaseModel):
    problem: str
    context: Optional[str] = None

@router.post("/analyze")
async def analyze_problem(request: DiagnosticRequest):
    # Implementar análise com OpenAI
    pass
```

#### 4.3 Criar `backend/app/api/queue.py`
```python
from fastapi import APIRouter
from backend.core.agent_queue import AgentQueue

router = APIRouter(prefix="/api/queue", tags=["queue"])
queue = AgentQueue()

@router.get("/stats")
async def get_stats():
    return queue.get_stats()
```

---

### **FASE 5: Frontend Integration (8h) - DIA 3**

#### 5.1 Criar `frontend/src/services/agentService.ts`
```typescript
import API from './api'

export const agentService = {
  async executeSiteAutomation(site: string, objetivo: string, dryRun = false) {
    const response = await API.post('/api/agents/site-automation', {
      site,
      objetivo,
      dry_run: dryRun
    })
    return response.data
  }
}
```

#### 5.2 Criar componentes React
- `frontend/src/pages/Agents.tsx`
- `frontend/src/pages/Diagnostics.tsx`
- `frontend/src/components/AgentCard.tsx`
- `frontend/src/components/DiagnosticForm.tsx`

---

### **FASE 6: Environment & Config (2h) - DIA 3**

#### 6.1 Criar `NEXUS/.env` consolidado
```env
# Backend
PORT=8000
LOG_LEVEL=INFO

# OpenAI
OPENAI_API_KEY=sk-proj-...

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Google
GOOGLE_ADSENSE_ACCOUNT_ID=pub-...
GOOGLE_CLOUD_PROJECT=...

# Clerk
CLERK_SECRET_KEY=sk_test_...
CLERK_PUBLISHABLE_KEY=pk_test_...

# Database
DATABASE_URL=postgresql://...

# Frontend
VITE_API_URL=http://localhost:8000
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
```

#### 6.2 Criar `docker-compose.yml`
```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./backend:/app
      - ./data:/app/data
      - ./config:/app/config

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://backend:8000
    volumes:
      - ./frontend:/app

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: nexus
      POSTGRES_USER: nexus
      POSTGRES_PASSWORD: nexus_password
    ports:
      - "5432:5432"
```

---

### **FASE 7: Testing (4h) - DIA 4**

#### 7.1 Testar Backend
```powershell
cd C:\Users\Charles\Desktop\NEXUS\backend
python -m pytest tests/
```

#### 7.2 Testar Agentes
```powershell
python -c "from backend.agents import site_agent; print('✅ Site Agent OK')"
```

#### 7.3 Testar Frontend → Backend
```typescript
// Browser console
fetch('/api/health').then(r => r.json()).then(console.log)
fetch('/api/agents/site-automation', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({site: 'instagram', objetivo: 'test', dry_run: true})
}).then(r => r.json()).then(console.log)
```

---

### **FASE 8: Documentation (2h) - DIA 4**

#### 8.1 Criar `NEXUS/README.md`
#### 8.2 Criar `NEXUS/ARCHITECTURE.md`
#### 8.3 Criar `NEXUS/docs/API.md`
#### 8.4 Criar `NEXUS/docs/DEPLOYMENT.md`

---

### **FASE 9: Deploy Preparation (4h) - DIA 5**

#### 9.1 Criar `NEXUS/Dockerfile`
#### 9.2 Configurar Cloud Run
#### 9.3 Setup PostgreSQL (Cloud SQL)
#### 9.4 Deploy scripts

---

### **FASE 10: Go Live (2h) - DIA 5**

#### 10.1 Deploy backend
#### 10.2 Deploy frontend
#### 10.3 Smoke tests
#### 10.4 Monitor errors

---

## ✅ CHECKLIST DE MIGRAÇÃO

### Dia 1 (6h)
- [ ] Criar estrutura de pastas
- [ ] Backup dos projetos
- [ ] Copiar backend core
- [ ] Copiar agentes
- [ ] Copiar integrações
- [ ] Ajustar imports
- [ ] Testar imports

### Dia 2 (8h)
- [ ] Criar API agents
- [ ] Criar API diagnostics
- [ ] Criar API queue
- [ ] Testar endpoints
- [ ] Documentar APIs

### Dia 3 (10h)
- [ ] Criar services frontend
- [ ] Criar componentes React
- [ ] Integrar Clerk auth
- [ ] Configurar .env
- [ ] docker-compose.yml
- [ ] Testar integração

### Dia 4 (6h)
- [ ] Testes backend
- [ ] Testes frontend
- [ ] Testes E2E
- [ ] Documentação
- [ ] README atualizado

### Dia 5 (6h)
- [ ] Dockerfile
- [ ] Cloud Run config
- [ ] PostgreSQL setup
- [ ] Deploy staging
- [ ] Smoke tests
- [ ] Deploy production

---

## 🎯 MÉTRICAS DE SUCESSO

- ✅ Backend rodando em NEXUS/backend
- ✅ 6 agentes funcionando via API
- ✅ Frontend chamando backend com sucesso
- ✅ Stripe + AdSense operacionais
- ✅ Deploy em Cloud Run
- ✅ Documentação completa
- ✅ Marca única: NEXUS
- ✅ UX consistente

---

## 🚀 COMEÇAR AGORA

```powershell
# Passo 1: Criar estrutura
cd C:\Users\Charles\Desktop\NEXUS
.\scripts\migrate_codex.ps1

# Passo 2: Testar
cd backend
python -m uvicorn main:app --reload

# Passo 3: Frontend
cd ..\frontend
npm run dev
```

---

**🎉 MIGRAÇÃO INICIADA - RUMO AO NEXUS UNIFICADO!**

*Documento de planejamento criado em 4 de Janeiro de 2026*
