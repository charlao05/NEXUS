# 🔄 ROTACAO DE CREDENCIAIS - GUIA EXECUTIVO

**STATUS**: CRÍTICO - Executar ANTES de colocar NEXUS em produção
**DATA**: 27 de Dezembro de 2025
**TEMPO ESTIMADO**: 15-20 minutos

---

## 🚨 IMPORTANTE

As credenciais abaixo foram usadas em ambiente de desenvolvimento no Replit:
- Mercado Pago Client ID / Secret / Public Key
- OpenAI API Key

**Embora NENHUMA esteja exposta no repositório GitHub**, recomenda-se **ROTACIONÁ-LAS POR PRECAUÇÃO**.

---

## PASSO 1: 💳 MERCADO PAGO - Regenerar Credenciais (URGENTE)

### Por quê?
Credenciais de desenvolvimento foram usadas. Precisam ser regeneradas para produção.

### Passos:

1. **Acesse o Dashboard Mercado Pago**
   - URL: https://www.mercadopago.com.br/developers
   - Login com sua conta

2. **Navegue para Credenciais**
   - Menu esquerdo: **Aplicações**
   - Selecione: **Suas Aplicações**
   - Clique na aplicação "NEXUS"

3. **Regenere Client ID**
   - Seção: "Credenciais de Produção"
   - Botão: **Regenerar Client ID**
   - Copie o novo valor
   - **SALVE EM LOCAL SEGURO** (ex: 1Password, LastPass)
   ```
   ANTIGO: 1580334838589391
   NOVO: [COPIE AQUI]
   ```

4. **Regenere Client Secret**
   - Botão: **Regenerar Client Secret**
   - Copie o novo valor
   - **SALVE EM LOCAL SEGURO**
   ```
   ANTIGO: ####hidden####
   NOVO: [COPIE AQUI]
   ```

5. **Regenere Public Key**
   - Botão: **Regenerar Public Key**
   - Copie o novo valor
   - **SALVE EM LOCAL SEGURO**

6. **Regenere Access Token** (se disponível)
   - Botão: **Regenerar Access Token**
   - Copie o novo valor

7. **Desative as credenciais antigas**
   - Se houver opção "Desativar", clique
   - Confirme a desativação

### Onde usar as novas credenciais:

**GitHub Secrets** (se usar GitHub Actions):
```bash
GH_SECRET_MERCADO_PAGO_CLIENT_ID = [NOVO]
GH_SECRET_MERCADO_PAGO_CLIENT_SECRET = [NOVO]
GH_SECRET_MERCADO_PAGO_PUBLIC_KEY = [NOVO]
GH_SECRET_MERCADO_PAGO_ACCESS_TOKEN = [NOVO]
```

**Railway / Vercel / Seu Hosting**:
```
MERCADO_PAGO_CLIENT_ID = [NOVO]
MERCADO_PAGO_CLIENT_SECRET = [NOVO]
MERCADO_PAGO_PUBLIC_KEY = [NOVO]
MERCADO_PAGO_ACCESS_TOKEN = [NOVO]
```

### Teste:
```bash
# Faça um teste de pagamento PIX em produção
# Confirme que funciona com as novas credenciais
```

**Status**: [ ] Concluído

---

## PASSO 2: 👋 OpenAI - Regenerar API Key (URGENTE)

### Por quê?
API Key de desenvolvimento foi armazenada. Precisar ser rotacionada para máxima segurança.

### Passos:

1. **Acesse OpenAI API Keys**
   - URL: https://platform.openai.com/account/api-keys
   - Login com sua conta

2. **Encontre sua chave anterior**
   - Procure por chaves com nome "NEXUS-Replit" ou similar
   - Verifique a data de criação

3. **Delete/Revogue a chave antiga**
   - Clique nos 3 pontinhos (...) na chave
   - Selecione **Delete** ou **Revoke**
   - Confirme a deleção
   - **A chave será desativada IMEDIATAMENTE**

4. **Crie uma nova chave**
   - Botão: **Create new secret key**
   - Nome: `NEXUS-Production`
   - Clique em "Create secret key"

5. **Copie a nova chave**
   - ⚠️ **COPIE AGORA** - não será exibida novamente
   - **SALVE EM LOCAL SEGURO**
   ```
   NOVA: [COPIE AQUI - sk-...]
   ```

### Onde usar a nova chave:

**GitHub Secrets**:
```bash
GH_SECRET_OPENAI_API_KEY = [NOVA]
```

**Railway / Vercel / Seu Hosting**:
```
AI_INTEGRATIONS_OPENAI_API_KEY = [NOVA]
```

### Teste:
```bash
# Faça uma chamada de API simples
# Exemplo: curl -H "Authorization: Bearer [NOVA]" https://api.openai.com/v1/models
# Confirme que funciona
```

**Status**: [ ] Concluído

---

## PASSO 3: ✅ Google AdSense Publisher ID - SEM AÇÃO NECESSÁRIA

### Por quê?
Publisher ID (ex: `ca-pub-6398044152546096`) é **PÚBLICO POR DESIGN**.

### Facts:
- É apenas um **identificador**, não uma senha
- Não oferece acesso a senhas, tokens ou dados sensíveis
- Pode estar em qualquer página HTML pública
- **NÃO PRECISA SER ROTACIONADO**

**Status**: [ ] Verificado (sem ação)

---

## FINAL: 📚 Checklist de Conclusão

- [ ] Mercado Pago: Novas credenciais GERADAS
- [ ] Mercado Pago: Credenciais ANTIGAS revogadas
- [ ] Mercado Pago: Novas credenciais SALVAS em local seguro
- [ ] Mercado Pago: Novas credenciais CONFIGURADAS em produção
- [ ] Mercado Pago: TESTE de pagamento realizado com sucesso
- [ ] OpenAI: Nova API Key GERADA
- [ ] OpenAI: Chave ANTIGA revogada/deletada
- [ ] OpenAI: Nova chave SALVA em local seguro
- [ ] OpenAI: Nova chave CONFIGURADA em produção
- [ ] OpenAI: TESTE de API realizado com sucesso
- [ ] Google AdSense: VERIFICADO (não precisa rotar)
- [ ] Todos os ambientes (GitHub Secrets, Railway, etc) ATUALIZADOS
- [ ] NEXUS pronto para PRODUÇÃO com segurança máxima

---

## 📧 Referências

- [Mercado Pago - Credenciais](https://www.mercadopago.com.br/developers)
- [OpenAI - API Keys](https://platform.openai.com/account/api-keys)
- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)

---

**⚠️ LEMBRETE**: Depois de completar esta checklist, o NEXUS estará **100% SEGURO** para produção! 🚀
