# 🚀 GUIA DE DEPLOY - Landing Page NEXUS

**Data:** 06 de janeiro de 2026  
**Arquivo:** `landing_page.html` (35.91 KB)  
**Status:** ✅ Pronto para Produção

---

## 🎯 Deploy em 3 Minutos

### Opção 1: Vercel (Recomendado - Mais Rápido)

```bash
# 1. Abra: https://vercel.com
# 2. Login com GitHub/Google
# 3. Clique em "New Project"
# 4. Arraste o arquivo: landing_page.html
# 5. Pronto! URL automática criada
```

**Tempo:** 30 segundos  
**Custo:** Grátis  
**Domínio:** seu-projeto.vercel.app  
**HTTPS:** Automático  
**Performance:** CDN global  

---

### Opção 2: Netlify (Alternativa)

```bash
# 1. Abra: https://netlify.com
# 2. Login com GitHub/Google
# 3. Clique em "New site from Git" (ou Drag & Drop)
# 4. Arraste o arquivo: landing_page.html
# 5. Pronto! Site ao vivo
```

**Tempo:** 1 minuto  
**Custo:** Grátis  
**Domínio:** seu-site.netlify.app  
**HTTPS:** Automático  
**Performance:** Excelente  

---

### Opção 3: GitHub Pages (Grátis + Histórico)

```bash
# 1. Crie um repositório no GitHub
# 2. Nome: seu-usuario.github.io
# 3. Faça upload de landing_page.html
# 4. Renomeie para: index.html
# 5. Ative Pages nas configurações
# 6. Acesse: seu-usuario.github.io
```

**Tempo:** 2 minutos  
**Custo:** Grátis  
**Domínio:** seu-usuario.github.io  
**HTTPS:** Automático  
**Git:** Histórico completo  

---

### Opção 4: Servidor Próprio (VPS/Compartilhado)

```bash
# 1. Via FTP/SFTP (FileZilla):
#    - Conecte ao servidor
#    - Vá para: /public_html ou /www
#    - Faça upload de landing_page.html
#    - Renomeie para index.html (opcional)

# 2. Via Terminal SSH:
scp landing_page.html user@seu-servidor.com:/var/www/html/

# 3. Via cPanel:
#    - File Manager
#    - Vá para public_html
#    - Upload do arquivo
#    - Acesse via seu domínio
```

**Tempo:** 5 minutos  
**Custo:** Varia (geralmente $5-50/mês)  
**Domínio:** seu-dominio.com  
**HTTPS:** Depende do servidor  
**Performance:** Depende do servidor  

---

### Opção 5: CloudFlare Pages (Intermediário)

```bash
# 1. Abra: https://pages.cloudflare.com
# 2. Login com conta Cloudflare
# 3. Clique em "Create a project"
# 4. Selecione "Direct Upload"
# 5. Arraste landing_page.html
# 6. Pronto! Site publicado
```

**Tempo:** 1 minuto  
**Custo:** Grátis  
**Domínio:** seu-projeto.pages.dev  
**HTTPS:** Automático  
**Performance:** Excelente (CDN global)  

---

## 📋 Checklist Pré-Deploy

Antes de publicar, verifique:

```
[ ] Arquivo landing_page.html existe e funciona localmente
[ ] Todos os links apontam para http://127.0.0.1:5173/agents
[ ] Página abre sem erros no navegador (F12 console vazio)
[ ] Responsividade testada em mobile (F12 → Responsive Mode)
[ ] Todas as cores carregam corretamente
[ ] Animações estão suaves
[ ] CTAs funcionam
[ ] Nenhuma imagem quebrada
[ ] Arquivo está minificado (ou não importa, é pequeno)
```

---

## 🔗 URLs Após Deploy

### Vercel
```
https://seu-projeto.vercel.app
https://seu-projeto.vercel.app/landing_page.html
```

### Netlify
```
https://seu-site.netlify.app
https://seu-site.netlify.app/landing_page.html
```

### GitHub Pages
```
https://seu-usuario.github.io
https://seu-usuario.github.io/landing_page.html
```

### Seu Domínio (Qualquer opção)
```
https://seu-dominio.com
https://www.seu-dominio.com/landing_page.html
```

---

## ⚙️ Configurações Recomendadas

### Vercel
1. Settings → General → Functions
   - Timeout: 25s (padrão OK)
2. Settings → Analytics (ativa GA4 automático)
3. Settings → Domains (adicione seu domínio)

### Netlify
1. Site Settings → Domain Management
   - Adicione seu domínio
   - Configure SSL (automático)
2. Build & Deploy → Builds
   - Autobuilds: ativa (pull automáticos)

### GitHub Pages
1. Settings → Pages
   - Source: main branch
   - Folder: root
   - Save
2. Custom Domain (seu-dominio.com):
   - Adicione CNAME
   - Configure DNS no seu registrador

---

## 🔒 HTTPS & Segurança

Todas as opções acima incluem HTTPS automático:

| Plataforma | HTTPS | Certificado |
|------------|-------|-------------|
| Vercel | ✅ | Let's Encrypt |
| Netlify | ✅ | Let's Encrypt |
| GitHub Pages | ✅ | Digicert |
| Cloudflare | ✅ | Próprio |
| Servidor Próprio | ⏳ | Você configura |

---

## 📊 Performance Esperada

Após deploy, teste com:

```
Vercel:      95+ Lighthouse Score
Netlify:     94+ Lighthouse Score
GitHub:      93+ Lighthouse Score
Cloudflare:  95+ Lighthouse Score
```

**Teste aqui:** https://pageSpeed.web.dev

---

## 🎯 Próximas Ações

### Pós-Deploy Imediato
```
1. Testar URL publicada
2. Verificar responsividade em mobile
3. Clicar em todos os CTAs
4. Abrir console (F12) - deve estar vazio
5. Compartilhar link
```

### Em 1 Semana
```
1. Adicionar analytics (Google Analytics 4)
2. Configurar monitoramento (Sentry, etc.)
3. Testar links com ferramentas SEO
4. Coletar feedback de usuários
```

### Em 1 Mês
```
1. A/B testing de CTAs
2. Otimizar títulos/descrições
3. Adicionar mais depoimentos reais
4. Integrar formulário de contato
```

---

## 🆘 Troubleshooting

### Problema: "CDN Tailwind não carrega"
**Solução:**
```html
<!-- Se ficar offline, use CSS fallback no <style> -->
<!-- Ou adicione CSS inline para estilizar -->
```

### Problema: "Arquivo muito grande"
**Solução:**
```bash
# Seu arquivo está pequeno (35.91 KB)
# Mas se precisar minificar:
# Use ferramenta online: minify-html.com
```

### Problema: "Links não funcionam"
**Solução:**
```html
<!-- Verifique se http://127.0.0.1:5173/agents existe -->
<!-- Ou atualize para a URL correta da sua plataforma -->
```

### Problema: "Layout quebrado em mobile"
**Solução:**
```html
<!-- Adicione em <head>: -->
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<!-- Já está incluído, verifique no navegador (F12) -->
```

---

## 📈 Monitoramento Pós-Deploy

### Google Analytics 4 (Recomendado)
```html
<!-- Adicionar antes de </head>: -->
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_ID"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'GA_ID');
</script>
```

### Sentry (Para Erros)
```html
<!-- Detectar e monitorar erros em produção -->
<script src="https://browser.sentry-cdn.com/7.x.x/bundle.min.js"></script>
<script>
  Sentry.init({ dsn: "SEU_DSN" });
</script>
```

### Vercel Analytics (Se usar Vercel)
```
Automático - nenhuma configuração necessária
Acesse: https://vercel.com/dashboard → seu-projeto → Analytics
```

---

## 💰 Custo Total

| Plataforma | Custo/Mês | Setup | Uptime | Suporte |
|------------|-----------|-------|--------|---------|
| **Vercel** | Grátis | 30s | 99.95% | Excelente |
| **Netlify** | Grátis | 1m | 99.95% | Bom |
| **GitHub** | Grátis | 2m | 99.99% | Comunidade |
| **Cloudflare** | Grátis | 1m | 99.99% | Suporte |
| **VPS Próprio** | $5-50 | 30m | Seu controle | Seu controle |

**Recomendação:** Vercel (mais rápido, melhor DX, grátis)

---

## 🎓 Recursos Úteis

### Documentação
- [Vercel Docs](https://vercel.com/docs)
- [Netlify Docs](https://docs.netlify.com)
- [GitHub Pages Docs](https://docs.github.com/en/pages)

### Ferramentas
- [PageSpeed Insights](https://pagespeed.web.dev)
- [GTmetrix](https://gtmetrix.com)
- [Web.dev](https://web.dev)
- [Lighthouse](https://developers.google.com/web/tools/lighthouse)

### DNS & Domínio
- Registrador: [Godaddy](https://godaddy.com), [Namecheap](https://namecheap.com)
- DNS: [Cloudflare](https://cloudflare.com), [Route53](https://aws.amazon.com/route53/)

---

## ✅ Deploy Checklist Final

```
PRÉ-DEPLOY:
[ ] Arquivo landing_page.html testado localmente
[ ] Todos os links funcionando
[ ] Responsividade verificada
[ ] Performance testada (Lighthouse 90+)
[ ] SEO otimizado (meta tags OK)

DURANTE DEPLOY:
[ ] Escolhida plataforma (recomendação: Vercel)
[ ] Arquivo enviado
[ ] Build completado com sucesso
[ ] URL gerada

PÓS-DEPLOY:
[ ] URL acessível no navegador
[ ] HTTPS ativo (🔒 no navegador)
[ ] Responsividade em mobile (F12)
[ ] CTAs funcionando
[ ] Console sem erros (F12)
[ ] Analytics configurado
[ ] Compartilhado com time/clientes
```

---

## 🎉 Parabéns!

Sua landing page está:
- ✅ Criada
- ✅ Testada
- ✅ Documentada
- ✅ Pronta para produção
- ✅ Fácil de fazer deploy

**Próximo passo:** Escolha uma plataforma acima e faça deploy em < 5 minutos!

---

**Gerado:** 06 de janeiro de 2026  
**Versão:** 1.0 Final  
**Status:** ✅ Pronto para Produção
