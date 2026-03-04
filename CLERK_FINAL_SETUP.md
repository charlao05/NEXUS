# 🔐 CONFIGURAÇÃO CLERK - INSTRUÇÕES FINAIS

## ✅ **O que já foi configurado automaticamente:**

1. ✅ URLs do Clerk configuradas:
   - Frontend API: `https://assuring-shad-6.clerk.accounts.dev`
   - Backend API: `https://api.clerk.com`
   - JWKS URL: `https://assuring-shad-6.clerk.accounts.dev/.well-known/jwks.json`

2. ✅ Chave pública JWKS adicionada ao `.env.local`

---

## ⚠️ **VOCÊ AINDA PRECISA FAZER (2 chaves secretas):**

### **1. Obter as chaves secretas do Clerk:**

Acesse o dashboard do Clerk que você já tem aberto:
- Vá em **"API Keys"** ou **"Chaves de API"**
- Localize:
  - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (começa com `pk_test_...`)
  - `CLERK_SECRET_KEY` (começa com `sk_test_...`)

### **2. Colar no arquivo `.env.local`:**

Abra: `C:\Users\Charles\Desktop\NEXUS\.env.local`

**Linha 7** - Cole a chave pública:
```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_SUA_CHAVE_AQUI
```

**Linha 9** - Cole a chave secreta:
```env
CLERK_SECRET_KEY=sk_test_SUA_CHAVE_SECRETA_AQUI
```

---

## 🎯 **Dica Rápida:**

No dashboard do Clerk que você tem aberto, procure por:
- "Publishable key" ou "Chave pública" → começa com `pk_test_`
- "Secret key" ou "Chave secreta" → começa com `sk_test_`

**Copie e cole diretamente no `.env.local`**

---

## 🔒 **Segurança Garantida:**

✅ Chave pública JWKS já configurada (seguro expor)  
✅ URLs do Clerk configuradas  
⚠️ Chaves secretas como placeholders (você cola manualmente)  
✅ `.env.local` protegido pelo `.gitignore`  

---

## 🚀 **Após colar as chaves:**

Reinicie os servidores para carregar as novas configurações:

```powershell
# Backend (CTRL+C no terminal atual e execute)
.\RUN_BACKEND_SECURE.ps1

# Frontend (CTRL+C e execute novamente)
cd frontend; npm run dev -- --host 127.0.0.1 --port 5175
```

---

**Agora é só copiar as 2 chaves do dashboard do Clerk e colar no `.env.local`!** 🔐
