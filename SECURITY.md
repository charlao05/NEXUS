# 🔒 GUIA DE SEGURANÇA - NEXUS

## STATUS DE SEGURANÇA

✅ **Repositório Seguro**
- Apenas arquivos públicos (README.md, .gitignore, SECURITY.md)
- Nenhuma credencial exposta
- .gitignore robusto protegendo secretos
- Histórico Git limpo

## ⚠️ ROTAÇÃO DE CREDENCIAIS (Recomendado)

Embora nenhuma credencial esteja visível no repositório, recomenda-se rotacioná-las por precaução após a migração do Replit.

### 1. 🔄 Mercado Pago - Regenerar Credenciais

**Status**: CRÍTICO - Credenciais foram usadas em ambiente de desenvolvimento

**Passos**:
1. Acesse [Mercado Pago Dashboard](https://www.mercadopago.com.br/developers)
2. Vá para **Aplicações** > **Suas Aplicações**
3. Selecione sua aplicação NEXUS
4. Em **Credenciais de Produção**:
   - Clique em **Regenerar Client ID** (salve o novo valor)
   - Clique em **Regenerar Client Secret** (salve o novo valor)
   - Clique em **Regenerar Public Key** (salve o novo valor)
5. Atualize as variáveis de ambiente no seu novo ambiente de deploy:
   - `MERCADO_PAGO_CLIENT_ID`
   - `MERCADO_PAGO_CLIENT_SECRET`
   - `MERCADO_PAGO_PUBLIC_KEY`
   - `MERCADO_PAGO_ACCESS_TOKEN`
6. Desative as credenciais antigas se houver opção

**Validação**: Faça um teste de pagamento em produção para confirmar

---

### 2. 🔄 OpenAI - Regenerar API Key

**Status**: CRÍTICO - API Key era acessível no Replit

**Passos**:
1. Acesse [OpenAI Platform](https://platform.openai.com/account/api-keys)
2. Procure sua chave API anterior (pode estar com nome tipo "NEXUS-Replit")
3. Clique em **Delete** ou **Revoke** para desativar
4. Clique em **Create new secret key**
5. Nomeie como "NEXUS-Production"
6. Copie a nova chave imediatamente
7. Atualize em seu ambiente de deploy:
   - `AI_INTEGRATIONS_OPENAI_API_KEY`
8. **NUNCA** coloque em .env files públicos

**Validação**: Teste uma chamada de API com a nova chave

---

### 3. ✅ Google AdSense Publisher ID - SEGURO

**Status**: SEGURO - Publisher ID não é credencial secreta

- Publisher ID (`ca-pub-xxxxxxxxxxxxxxxx`) é **público por design**
- É apenas um identificador, NÃO uma senha ou token
- Não oferece acesso a nenhum recurso sensível
- **NÃO precisa ser rotacionado**

---

## 🛡️ Melhores Práticas para o Futuro

### Nunca fazer commit de:
```
.env files
Secrets ou API keys
.credentials ou .keys arquivos
Variáveis de ambiente locais
```

### Sempre usar:
```
.gitignore (incluído neste repo)
Environment variables em produção
Secrets Manager (GitHub Secrets, Vercel, etc)
Variables privadas no seu ambiente de deploy
```

### Se uma credencial for exposta:
1. **IMEDIATAMENTE** desative/revogue no serviço correspondente
2. Regenere uma nova
3. Atualize em seu ambiente de deploy
4. Force um novo deploy
5. Monitore por atividades suspeitas

---

## 📊 Checklist de Rotação

- [ ] Mercado Pago: Novas credenciais geradas
- [ ] Mercado Pago: Credenciais antigas revogadas
- [ ] Mercado Pago: Novas credenciais atualizadas em produção
- [ ] OpenAI: Nova API Key gerada
- [ ] OpenAI: Chave antiga revogada
- [ ] OpenAI: Nova chave atualizada em produção
- [ ] Testes funcionais completados
- [ ] Monitoramento de atividades suspeitas

---

## 📞 Contato e Suporte

Para questões de segurança:
- Email: `support@nexus.app`
- GitHub Issues: Use label `security`

---

**Última atualização**: 27 de Dezembro de 2025
**Versão**: 1.0
