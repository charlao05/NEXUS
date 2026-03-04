# Configuração para Produção - NEXUS

## 1. Google OAuth (Login com Google)

Para o login com Google funcionar, você precisa configurar no Google Cloud Console:

### Passo a passo:
1. Acesse: https://console.cloud.google.com/apis/credentials
2. Use o projeto existente: `agendamento-n8n-476415`
3. Vá em **OAuth consent screen**:
   - Tipo: **External**
   - Nome do app: NEXUS
   - Email de suporte: seu email
   - Domínios autorizados: seu domínio de produção
   - Clique em **Salvar**

4. Crie credenciais OAuth:
   - Clique em **Criar credenciais** > **ID do cliente OAuth**
   - Tipo: **Aplicativo da Web**
   - Nome: NEXUS Login
   - URIs de redirecionamento autorizados:
     - `http://localhost:8000/api/auth/google/callback` (dev)
     - `https://seu-backend.com/api/auth/google/callback` (produção)

5. Copie o **Client ID** e **Client Secret** para o `.env`:
```env
GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=seu-client-secret
```

---

## 2. Stripe (Pagamentos)

### Para testes:
Use as chaves de teste (já configuradas):
- `STRIPE_SECRET_KEY=sk_test_...`
- `STRIPE_PUBLISHABLE_KEY=pk_test_...`

### Para produção (Play Store):
1. Acesse: https://dashboard.stripe.com/apikeys
2. Ative o modo **Live**
3. Copie as chaves de produção:
```env
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_MODE=production
```

4. Configure webhooks em: https://dashboard.stripe.com/webhooks
   - Endpoint: `https://seu-backend.com/api/auth/webhook/stripe`
   - Eventos: `checkout.session.completed`, `invoice.paid`

---

## 3. URLs de Produção

No `.env`, atualize para seus domínios:
```env
FRONTEND_URL=https://nexus.seudominio.com
BACKEND_BASE_URL=https://api.nexus.seudominio.com
```

---

## 4. Banco de Dados (Produção)

Atualmente está usando SQLite para testes. Para produção, configure PostgreSQL:
```env
DATABASE_URL=postgresql://user:password@host:5432/nexus_db
```

---

## 5. JWT Secret (IMPORTANTE!)

Gere uma chave segura para produção:
```powershell
[Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

Atualize no `.env`:
```env
JWT_SECRET=sua-chave-super-segura-gerada
```

---

## 6. Checklist Final antes da Play Store

- [ ] Google OAuth configurado e testado
- [ ] Stripe modo LIVE ativado
- [ ] JWT_SECRET atualizado (não usar valor de dev)
- [ ] Banco de dados PostgreSQL configurado
- [ ] HTTPS ativo em frontend e backend
- [ ] URLs de produção configuradas
- [ ] Política de privacidade publicada
- [ ] Termos de uso publicados

---

## Comandos para Iniciar em Dev

```powershell
# Terminal 1 - Backend
cd C:\Users\Charles\Desktop\NEXUS\backend
& C:\Users\Charles\Desktop\NEXUS\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 - Frontend
cd C:\Users\Charles\Desktop\NEXUS\frontend
npm run dev
```

Ou use o atalho: **NEXUS.lnk** na área de trabalho
