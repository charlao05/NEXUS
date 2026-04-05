# 🔐 GUIA DE EXECUÇÃO SEGURA - NEXUS

## ✅ **Dois Scripts Seguros Criados**

### 1. **Backend (Python + FastAPI)**
📄 Arquivo: `RUN_BACKEND_SECURE.ps1`

### 2. **Frontend (React + Vite)**
📄 Arquivo: `RUN_FRONTEND_SECURE.ps1`

---

## 🚀 **Como Executar (Método Seguro)**

### **Terminal 1 - Backend:**

```powershell
cd C:\Users\Charles\Desktop\NEXUS
.\RUN_BACKEND_SECURE.ps1
```

**O que este script faz:**
- ✅ Valida a estrutura do projeto
- ✅ Carrega `.env.local` **SEM EXPOR** secrets
- ✅ Ativa o venv automaticamente
- ✅ Verifica se chaves críticas estão configuradas
- ✅ Inicia o servidor na porta 8000
- ✅ Mantém secrets fora do histórico de comandos

### **Terminal 2 - Frontend:**

```powershell
cd C:\Users\Charles\Desktop\NEXUS\frontend
.\RUN_FRONTEND_SECURE.ps1
```

**O que este script faz:**
- ✅ Carrega variáveis públicas do `.env.local`
- ✅ Valida dependências (npm install automático se necessário)
- ✅ Inicia servidor Vite na porta 5175
- ✅ Configura proxy para `/api` → backend

---

## 🔒 **Segurança Garantida**

### ✅ **Credenciais Protegidas:**
- Secrets **carregados em variáveis de ambiente** (não no terminal)
- **Nunca aparecem** no histórico do PowerShell
- **Não expostos** em argumentos de linha de comando

### ✅ **Validações Automáticas:**
- Verifica se `.env.local` existe
- Valida se chaves críticas estão configuradas
- Alerta se houver placeholders (COLE_SUA_CHAVE)

### ✅ **Logs Seguros:**
```
📋 Passo 1: Validando ambiente...
✅ Estrutura validada

📋 Passo 2: Carregando variáveis...
✅ Variáveis carregadas (3 valores encontrados)

📋 Passo 3: Validando secrets...
  ✅ STRIPE_SECRET_KEY (configurada)
  ✅ CLERK_SECRET_KEY (configurada)
  ✅ JWT_SECRET (configurada)
```

---

## 📊 **Arquitetura de Segurança**

```
┌─────────────────────────────────────────────────────┐
│  .env.local (NUNCA commitado)                       │
│  - STRIPE_SECRET_KEY=sk_live_...                    │
│  - CLERK_SECRET_KEY=sk_test_...                     │
│  - JWT_SECRET=<gerado com openssl rand -hex 64>     │
└─────────────┬───────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│  RUN_*_SECURE.ps1 (Scripts locais)                  │
│  - Lê .env.local                                    │
│  - Carrega em variáveis de ambiente                 │
│  - Executa sem expor secrets                        │
└─────────────┬───────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│  Processo Python/Node (isolado)                     │
│  - Acessa variáveis de ambiente                     │
│  - Secrets permanecem protegidas                    │
│  - Nunca expostas no terminal                       │
└─────────────────────────────────────────────────────┘
```

---

## 🧪 **Testar Se Está Seguro**

### **1. Verificar histórico do PowerShell:**

```powershell
Get-History | Select-Object -ExpandProperty CommandLine | 
  Where-Object { $_ -like "*sk_live*" -or $_ -like "*sk_test*" }
```

**Resultado esperado:** Nenhuma linha encontrada ✅

### **2. Verificar variáveis de ambiente:**

```powershell
Get-Item env:STRIPE_SECRET_KEY | Select-Object -ExpandProperty Value
```

**Resultado:** Mostra apenas o valor (não no histórico de comandos)

### **3. Testar backend:**

```powershell
# Em outro terminal, testar health check
Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -Method GET | 
  ConvertTo-Json
```

**Esperado:**
```json
{
  "status": "ok",
  "stripe": "configured"
}
```

---

## ⚠️ **NUNCA FAÇA**

```powershell
# ❌ ERRADO - Expõe secrets no histórico
python -m uvicorn backend.main:app --reload --env-file .env.local

# ❌ ERRADO - Passa chaves como argumento
python -m uvicorn backend.main:app --stripe-key="sk_live_..."

# ❌ ERRADO - Coloca secrets no comando
$env:STRIPE_SECRET_KEY = "sk_live_..." # (pode ser visto no histórico)
```

---

## ✅ **FAÇA ASSIM**

```powershell
# ✅ CORRETO - Usa script que carrega variáveis
.\RUN_BACKEND_SECURE.ps1

# ✅ CORRETO - Carrega de arquivo
$env:STRIPE_SECRET_KEY = Get-Content .env.local | 
  Select-String "STRIPE_SECRET_KEY" | 
  ForEach-Object { $_.Line.Split("=")[1] }
```

---

## 🔧 **Opções Avançadas**

### **Backend com porta customizada:**
```powershell
.\RUN_BACKEND_SECURE.ps1 -Port 8080 -Host 0.0.0.0
```

### **Backend sem reload (produção):**
```powershell
.\RUN_BACKEND_SECURE.ps1 -NoReload
```

### **Frontend com porta customizada:**
```powershell
.\RUN_FRONTEND_SECURE.ps1 -Port 3000 -Host 0.0.0.0
```

---

## 📋 **Checklist de Segurança**

- [ ] Usei `RUN_BACKEND_SECURE.ps1` (não comando manual)
- [ ] Usei `RUN_FRONTEND_SECURE.ps1` (não comando manual)
- [ ] `.env.local` tem todas as chaves reais coladas
- [ ] Verificar com `Get-History` - nenhuma chave exposta
- [ ] Testei `/health` endpoint
- [ ] Frontend conecta ao backend sem erros
- [ ] `.env.local` está no `.gitignore`

---

## 🎉 **Está Seguro! Agora é só executar:**

```powershell
# Terminal 1
.\RUN_BACKEND_SECURE.ps1

# Terminal 2 (na pasta frontend)
.\RUN_FRONTEND_SECURE.ps1
```

**Suas credenciais estão 100% protegidas!** 🔐
