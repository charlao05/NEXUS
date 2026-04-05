# 🔐 GUIA DE CONFIGURAÇÃO SEGURA - NEXUS

## ✅ **Arquivos Criados**

1. **`.env.local`** - Configuração local (cole suas chaves aqui)
2. **`.env.template`** - Template para referência
3. **`.gitignore`** - Já protege arquivos sensíveis ✅

---

## 📝 **PRÓXIMOS PASSOS - PREENCHA AS CHAVES**

### **1. Stripe**
Acesse: https://dashboard.stripe.com/apikeys

Cole as chaves em `.env.local`:
```env
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_COLE_SUA_CHAVE_PUBLICA_AQUI
STRIPE_SECRET_KEY=sk_live_... (cole a chave secreta completa)
```

### **2. Clerk**
Acesse: https://dashboard.clerk.com

Cole as chaves em `.env.local`:
```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_... (cole a chave pública)
CLERK_SECRET_KEY=sk_test_... (cole a chave secreta)
```

### **3. OpenAI** (se usar)
Acesse: https://platform.openai.com/api-keys

```env
OPENAI_API_KEY=sk-... (cole sua chave)
```

### **4. JWT Secret** (gere uma chave aleatória)
No PowerShell:
```powershell
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | % {[char]$_})
```

Cole o resultado em:
```env
JWT_SECRET=<resultado_aqui>
```

---

## 🔒 **SEGURANÇA GARANTIDA**

✅ `.env.local` está no `.gitignore` - NUNCA será commitado
✅ Template criado para referência sem expor secrets
✅ Placeholders claros indicam onde colar as chaves
✅ Estrutura seguindo melhores práticas

---

## 🚀 **VERIFICAR CONFIGURAÇÃO**

Após preencher as chaves:

### Backend:
```powershell
cd C:\Users\Charles\Desktop\NEXUS
& .venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend:
```powershell
cd C:\Users\Charles\Desktop\NEXUS\frontend
npm run dev -- --host 127.0.0.1 --port 5175
```

### Teste:
```
http://127.0.0.1:8000/health  (deve retornar "stripe": "configured")
http://127.0.0.1:5175         (frontend deve carregar com Clerk)
```

---

## ⚠️ **NUNCA FAÇA**

❌ Commitar `.env.local` no Git
❌ Compartilhar chaves em mensagens/chat
❌ Usar chaves de produção em desenvolvimento
❌ Expor secrets em logs

---

## ✅ **CHECKLIST FINAL**

- [ ] `.env.local` criado na raiz do NEXUS
- [ ] Chaves do Stripe coladas
- [ ] Chaves do Clerk coladas
- [ ] JWT Secret gerado e colado
- [ ] OpenAI API Key colada (se usar)
- [ ] Backend rodando sem erros
- [ ] Frontend rodando sem erros
- [ ] Endpoint `/health` retorna "configured"

---

**Está tudo pronto! Agora é só colar suas chaves reais no `.env.local` e rodar os serviços.** 🚀
