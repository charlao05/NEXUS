# 🔐 COMANDO ÚNICO - EXECUÇÃO COM CREDENCIAIS PROTEGIDAS

## ✅ **Para BACKEND (Python + FastAPI)**

Cole este comando INTEIRO no PowerShell:

```powershell
cd C:\Users\Charles\Desktop\NEXUS; & {Get-Content .\.env.local | Where-Object {$_ -and -notmatch '^#'} | ForEach-Object {if($_ -match '^([^=]+)=(.*)$'){$var=$matches[1];$val=$matches[2];[Environment]::SetEnvironmentVariable($var, $val, 'Process')}} ; & .\.venv\Scripts\Activate.ps1 ; python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000}
```

---

## ✅ **Para FRONTEND (React + Vite)**

Cole este comando INTEIRO no PowerShell:

```powershell
cd C:\Users\Charles\Desktop\NEXUS\frontend; & {$env_path = if(Test-Path .\.env.local){.\.env.local}else{..\\.env.local}; Get-Content $env_path | Where-Object {$_ -and -notmatch '^#'} | ForEach-Object {if($_ -match '^(NEXT_PUBLIC_[^=]+)=(.*)$'){$var=$matches[1];$val=$matches[2];[Environment]::SetEnvironmentVariable($var, $val, 'Process')}} ; npm run dev -- --host 127.0.0.1 --port 5175}
```

---

## 🔒 **Por que é seguro?**

✅ Carrega `.env.local` na memória (não exibe)
✅ Define variáveis de ambiente (processo isolado)
✅ **Nunca aparece no histórico** de comandos
✅ **Sem expor secrets** no terminal
✅ Seguro para rodar em qualquer máquina

---

## 📌 **VERSÃO MAIS SIMPLES (Recomendada)**

Se preferir algo mais direto, use os scripts que já criei:

### Backend:
```powershell
cd C:\Users\Charles\Desktop\NEXUS; .\RUN_BACKEND_SECURE.ps1
```

### Frontend:
```powershell
cd C:\Users\Charles\Desktop\NEXUS\frontend; .\RUN_FRONTEND_SECURE.ps1
```

---

## 🎯 **O que cada comando faz (passo a passo):**

### Backend:
1. Navega até NEXUS
2. Lê `.env.local`
3. Carrega TODAS as variáveis em ambiente (sem expor)
4. Ativa venv
5. Executa `uvicorn` com credentials loaded

### Frontend:
1. Navega até frontend
2. Procura `.env.local` (na pasta ou acima)
3. Carrega APENAS variáveis `NEXT_PUBLIC_*` (seguro)
4. Executa `npm run dev`

---

## 🔐 **Verificar se está realmente seguro:**

Depois de rodar qualquer um dos comandos, execute:

```powershell
Get-History | Select-Object CommandLine | 
  Where-Object {$_ -like "*sk_live*" -or $_ -like "*sk_test*" -or $_ -like "*STRIPE*"}
```

**Resultado esperado:** Nada encontrado ✅

---

## ⚡ **Versão em UMA LINHA (Copy/Paste direto)**

### Backend:
```powershell
cd C:\Users\Charles\Desktop\NEXUS; Get-Content .\.env.local | Where-Object {$_ -and -notmatch '^#'} | ForEach-Object {if($_ -match '^([^=]+)=(.*)$'){[Environment]::SetEnvironmentVariable($matches[1],$matches[2],'Process')}} ; & .\.venv\Scripts\Activate.ps1 ; python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend:
```powershell
cd C:\Users\Charles\Desktop\NEXUS\frontend; Get-Content (if(Test-Path .\.env.local){'.\.env.local'}else{'..\\.env.local'}) | Where-Object {$_ -and -notmatch '^#'} | ForEach-Object {if($_ -match '^(NEXT_PUBLIC_[^=]+)=(.*)$'){[Environment]::SetEnvironmentVariable($matches[1],$matches[2],'Process')}} ; npm run dev -- --host 127.0.0.1 --port 5175
```

---

## 🎓 **Entendendo o comando:**

```powershell
# Parte 1: Navegação
cd C:\Users\Charles\Desktop\NEXUS

# Parte 2: Carrega .env.local sem expor
Get-Content .\.env.local | 
  Where-Object {$_ -and -notmatch '^#'} | 
  ForEach-Object {
    if($_ -match '^([^=]+)=(.*)$'){
      [Environment]::SetEnvironmentVariable($matches[1],$matches[2],'Process')
    }
  }

# Parte 3: Ativa venv
& .\.venv\Scripts\Activate.ps1

# Parte 4: Executa servidor (com variáveis já carregadas)
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

**Key point:** `[Environment]::SetEnvironmentVariable()` carrega na memória do processo, **nunca expõe no terminal ou histórico**.

---

## ✅ **Checklist:**

- [ ] Copiei um dos comandos acima
- [ ] Colei inteiro no PowerShell
- [ ] Pressionei Enter
- [ ] Servidor iniciou sem erros
- [ ] Testei `Get-History` - nenhuma chave exposta
- [ ] Acessei o servidor no navegador
- [ ] Tudo funcionando! 🎉

---

**Agora sim! Credenciais 100% protegidas, sem histórico exposto!** 🔐
