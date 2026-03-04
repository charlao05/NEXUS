# Prompt de Design para Landing Page NEXUS
## Estrutura Modular - Pronto para GitHub Copilot

---

## 📋 INSTRUÇÕES INICIAIS

Este prompt define **APENAS** aspectos visuais, estruturais e de layout.

O conteúdo real será **preenchido automaticamente** pelo GitHub Copilot usando dados do código-fonte do NEXUS.

Use placeholders genéricos como:
- `[TÍTULO_AGENTE]`
- `[DESCRIÇÃO_AGENTE]`
- `[FUNCIONALIDADES_AGENTE]`
- `[EMOJI_AGENTE]`

---

## 🎨 ESPECIFICAÇÕES DE DESIGN

### Paleta de Cores

```
Primária:           #3B82F6 (blue-500)
Primária Escura:    #2563EB (blue-600)
Secundária:         #8B5CF6 (purple-500)
Secundária Escura:  #7C3AED (purple-600)
Accent:             #06B6D4 (cyan-500)
Background:         #FFFFFF (white)
Background Alt:     #F9FAFB (gray-50)
Texto Principal:    #1F2937 (gray-800)
Texto Secundário:   #6B7280 (gray-500)
```

### Gradientes Padrão

```
Hero:       bg-gradient-to-br from-blue-50 via-purple-50 to-cyan-50
CTAs:       bg-gradient-to-r from-blue-600 to-purple-600
Seções:     Alternar branco e gray-50
```

### Cores por Agente (Crítico)

```
Agente 1 - Automação Web:    from-blue-500 to-blue-600
Agente 2 - Agenda:            from-purple-500 to-purple-600
Agente 3 - Clientes:          from-cyan-500 to-cyan-600
Agente 4 - Financeiro:        from-green-500 to-green-600
Agente 5 - Nota Fiscal:       from-indigo-500 to-indigo-600
Agente 6 - Cobranças:         from-pink-500 to-pink-600
```

---

## 📐 ESTRUTURA DE LAYOUT

### 1. NAVBAR (Fixo no Topo)

```html
<nav class="fixed top-0 w-full bg-white/90 backdrop-blur-md shadow-sm z-50">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex justify-between items-center h-16">
      <!-- Logo esquerda -->
      <!-- Menu centro (esconder em mobile) -->
      <!-- CTA direita -->
    </div>
  </div>
</nav>
```

**Especificações:**
- Altura: `h-16`
- Container: `max-w-7xl mx-auto`
- Padding: `px-4 sm:px-6 lg:px-8`
- Background: `bg-white/90 backdrop-blur-md`
- Sombra: `shadow-sm`
- Posição: `fixed top-0 z-50`

---

### 2. HERO SECTION

```html
<section class="pt-32 pb-16 lg:pt-40 lg:pb-24 bg-gradient-to-br from-blue-50 via-purple-50 to-cyan-50">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="text-center max-w-4xl mx-auto">
      <!-- H1: text-5xl lg:text-6xl font-bold -->
      <!-- Subtítulo: text-xl lg:text-2xl text-gray-600 -->
      <!-- CTAs: flex flex-col sm:flex-row gap-4 -->
      <!-- Badges: flex items-center justify-center gap-6 -->
    </div>
  </div>
</section>
```

**Especificações:**
- Padding vertical: `pt-32 pb-16 lg:pt-40 lg:pb-24`
- Conteúdo: `text-center max-w-4xl mx-auto`
- Título: `text-5xl lg:text-6xl font-bold mb-6`
- Subtítulo: `text-xl lg:text-2xl mb-8`
- CTAs: `gap-4 justify-center`
- Background: Gradiente suave

---

### 3. SOCIAL PROOF (Badges/Stats)

```html
<section class="py-12 bg-white border-b">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
      <!-- 3 cards com números/stats -->
    </div>
  </div>
</section>
```

**Especificações:**
- Grid: `grid-cols-1 md:grid-cols-3 gap-8`
- Alinhamento: `text-center`
- Números: `text-4xl font-bold`
- Labels: `text-gray-600`

---

### 4. SEÇÃO DE BENEFÍCIOS

```html
<section class="py-16 lg:py-24 bg-gray-50">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <h2 class="text-3xl lg:text-4xl font-bold text-center mb-12">[TÍTULO]</h2>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
      <!-- 3 cards de benefícios -->
    </div>
  </div>
</section>
```

**Card de Benefício:**
```html
<div class="bg-white rounded-xl shadow-lg p-8 hover:shadow-2xl transition-all min-h-[280px]">
  <div class="text-5xl mb-4">[EMOJI]</div>
  <h3 class="text-2xl font-semibold mb-3">[TÍTULO]</h3>
  <p class="text-gray-600 leading-relaxed">[DESCRIÇÃO]</p>
</div>
```

---

### 5. SHOWCASE DOS AGENTES (Principal) ⭐

```html
<section class="py-16 lg:py-24 bg-white">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="text-center mb-12">
      <h2 class="text-3xl lg:text-4xl font-bold mb-4">[TÍTULO]</h2>
      <p class="text-xl text-gray-600">[SUBTÍTULO]</p>
    </div>
    
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
      <!-- 6 cards de agentes -->
    </div>
  </div>
</section>
```

**ESTRUTURA DE CARD DE AGENTE (CRÍTICA):**

```html
<div class="bg-white rounded-xl shadow-md hover:shadow-2xl transition-all duration-300 overflow-hidden group">
  
  <!-- HEADER COLORIDO -->
  <div class="bg-gradient-to-r [GRADIENTE_COR_AGENTE] p-6 text-white">
    <div class="flex items-start justify-between mb-3">
      <div class="text-5xl">[EMOJI_AGENTE]</div>
      <span class="bg-white/20 backdrop-blur-sm px-3 py-1 rounded-full text-xs font-semibold">
        [BADGE_INFO]
      </span>
    </div>
    <h3 class="text-xl font-bold">[NOME_AGENTE]</h3>
  </div>

  <!-- BODY BRANCO -->
  <div class="p-6">
    <p class="text-gray-600 leading-relaxed mb-6">
      [DESCRIÇÃO_AGENTE]
    </p>

    <!-- LISTA DE FUNCIONALIDADES -->
    <ul class="space-y-2 mb-6">
      <li class="flex items-start text-sm text-gray-600">
        <svg class="w-5 h-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
        [FUNCIONALIDADE_1]
      </li>
      <li class="flex items-start text-sm text-gray-600">
        <svg class="w-5 h-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
        [FUNCIONALIDADE_2]
      </li>
      <li class="flex items-start text-sm text-gray-600">
        <svg class="w-5 h-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
        [FUNCIONALIDADE_3]
      </li>
    </ul>

    <!-- BOTÃO -->
    <button class="w-full bg-gradient-to-r [GRADIENTE_COR_AGENTE] text-white font-semibold py-3 rounded-lg hover:shadow-lg hover:scale-105 transition-all duration-300">
      [TEXTO_CTA]
    </button>
  </div>

</div>
```

**Especificações dos Cards:**
- Container: `bg-white rounded-xl shadow-md overflow-hidden`
- Hover: `hover:shadow-2xl transition-all duration-300`
- Header: `p-6`, gradiente colorido
- Body: `p-6`
- Lista: `space-y-2 mb-6`
- Ícone check: `w-5 h-5 text-green-500`
- Botão: `w-full py-3 rounded-lg`

---

### 6. COMO FUNCIONA (3 Passos)

```html
<section class="py-16 lg:py-24 bg-gray-50">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <h2 class="text-3xl lg:text-4xl font-bold text-center mb-16">[TÍTULO]</h2>
    
    <div class="grid grid-cols-1 md:grid-cols-3 gap-12">
      <div class="text-center">
        <div class="w-16 h-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full flex items-center justify-center text-white text-2xl font-bold mx-auto mb-4">
          1
        </div>
        <h3 class="text-xl font-semibold mb-3">[TÍTULO_PASSO_1]</h3>
        <p class="text-gray-600">[DESCRIÇÃO_PASSO_1]</p>
      </div>
      
      <div class="text-center">
        <div class="w-16 h-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full flex items-center justify-center text-white text-2xl font-bold mx-auto mb-4">
          2
        </div>
        <h3 class="text-xl font-semibold mb-3">[TÍTULO_PASSO_2]</h3>
        <p class="text-gray-600">[DESCRIÇÃO_PASSO_2]</p>
      </div>
      
      <div class="text-center">
        <div class="w-16 h-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full flex items-center justify-center text-white text-2xl font-bold mx-auto mb-4">
          3
        </div>
        <h3 class="text-xl font-semibold mb-3">[TÍTULO_PASSO_3]</h3>
        <p class="text-gray-600">[DESCRIÇÃO_PASSO_3]</p>
      </div>
    </div>
  </div>
</section>
```

**Layout dos Passos:**
- Número: `w-16 h-16`, gradiente, `rounded-full`, centralizado
- Grid: `grid-cols-1 md:grid-cols-3 gap-12`
- Alinhamento: `text-center`
- Espaçamento consistente

---

### 7. DEPOIMENTOS

```html
<section class="py-16 lg:py-24 bg-white">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <h2 class="text-3xl lg:text-4xl font-bold text-center mb-12">[TÍTULO]</h2>
    
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
      <div class="bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl p-6 shadow-lg">
        <div class="flex items-center mb-4">
          <div class="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center text-white font-bold mr-3">
            [INICIAL_1]
          </div>
          <div>
            <div class="font-semibold">[NOME_1]</div>
            <div class="text-sm text-gray-600">[CARGO_1]</div>
          </div>
        </div>
        <p class="text-gray-700 italic">"[DEPOIMENTO_1]"</p>
      </div>
      
      <div class="bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl p-6 shadow-lg">
        <div class="flex items-center mb-4">
          <div class="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center text-white font-bold mr-3">
            [INICIAL_2]
          </div>
          <div>
            <div class="font-semibold">[NOME_2]</div>
            <div class="text-sm text-gray-600">[CARGO_2]</div>
          </div>
        </div>
        <p class="text-gray-700 italic">"[DEPOIMENTO_2]"</p>
      </div>
      
      <div class="bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl p-6 shadow-lg">
        <div class="flex items-center mb-4">
          <div class="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center text-white font-bold mr-3">
            [INICIAL_3]
          </div>
          <div>
            <div class="font-semibold">[NOME_3]</div>
            <div class="text-sm text-gray-600">[CARGO_3]</div>
          </div>
        </div>
        <p class="text-gray-700 italic">"[DEPOIMENTO_3]"</p>
      </div>
    </div>
  </div>
</section>
```

---

### 8. CTA FINAL

```html
<section class="py-16 lg:py-24 bg-gradient-to-r from-blue-600 to-purple-600">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
    <h2 class="text-3xl lg:text-4xl font-bold text-white mb-4">
      [TÍTULO_CTA]
    </h2>
    <p class="text-xl text-blue-100 mb-8 max-w-2xl mx-auto">
      [SUBTÍTULO_CTA]
    </p>
    <a href="http://127.0.0.1:5173/agents" class="inline-block bg-white text-blue-600 px-8 py-4 rounded-lg font-semibold text-lg hover:shadow-2xl hover:scale-105 transition-all">
      [TEXTO_BOTÃO]
    </a>
    <div class="flex items-center justify-center gap-6 text-blue-100 text-sm mt-6">
      <span>✓ [GARANTIA_1]</span>
      <span>✓ [GARANTIA_2]</span>
      <span>✓ [GARANTIA_3]</span>
    </div>
  </div>
</section>
```

---

### 9. FOOTER

```html
<footer class="bg-gray-900 text-gray-400 py-12">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="text-center">
      <div class="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-4">
        NEXUS
      </div>
      <p class="mb-4">[TAGLINE]</p>
      <div class="flex justify-center space-x-6 mb-6">
        <a href="#" class="hover:text-white transition">[LINK_1]</a>
        <a href="#" class="hover:text-white transition">[LINK_2]</a>
        <a href="#" class="hover:text-white transition">[LINK_3]</a>
      </div>
      <p class="text-sm">© 2026 NEXUS. Todos os direitos reservados.</p>
    </div>
  </div>
</footer>
```

---

## 📏 GRID SYSTEM OBRIGATÓRIO

### Container Global

```html
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
  <!-- Conteúdo -->
</div>
```

### Grids Responsivos

```html
<!-- 3 Colunas -->
<div class="grid grid-cols-1 md:grid-cols-3 gap-8">
  <!-- Items -->
</div>

<!-- 2 Colunas -->
<div class="grid grid-cols-1 md:grid-cols-2 gap-8">
  <!-- Items -->
</div>
```

### Espaçamento Vertical

```
Seções:          py-16 lg:py-24
Entre Elementos: mb-4, mb-6, mb-8, mb-12, mb-16
Gaps:            gap-6 ou gap-8
```

---

## 🔤 TIPOGRAFIA

### Hierarquia

```
H1 (Hero):       text-5xl lg:text-6xl font-bold leading-tight
H2 (Seções):     text-3xl lg:text-4xl font-bold
H3 (Cards):      text-xl lg:text-2xl font-semibold
Body:            text-base lg:text-lg leading-relaxed
Small:           text-sm
```

### Fonte

```html
<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

<!-- Aplicar -->
<body class="font-['Inter']">
```

---

## 🎛️ COMPONENTES REUTILIZÁVEIS

### Botão Primário

```html
<button class="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-8 py-3 rounded-lg font-semibold hover:shadow-lg hover:scale-105 transition-all">
  [TEXTO]
</button>
```

### Botão Secundário

```html
<button class="bg-white border-2 border-blue-600 text-blue-600 px-8 py-3 rounded-lg font-semibold hover:bg-blue-50 transition">
  [TEXTO]
</button>
```

### Badge/Tag

```html
<span class="bg-blue-100 text-blue-800 text-sm font-medium px-3 py-1 rounded-full">
  [TEXTO]
</span>
```

### Check Item

```html
<li class="flex items-start text-sm text-gray-600">
  <svg class="w-5 h-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
  </svg>
  [TEXTO]
</li>
```

---

## ✨ ANIMAÇÕES

### Hover States

```html
<!-- Cards -->
<div class="hover:shadow-2xl hover:scale-105 transition-all duration-300">

<!-- Botões -->
<button class="hover:shadow-lg transition-all">

<!-- Links -->
<a class="hover:text-blue-600 transition">
```

### Scroll Animations (JavaScript)

```javascript
<script>
document.addEventListener('DOMContentLoaded', function() {
  // Smooth scroll
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      document.querySelector(this.getAttribute('href')).scrollIntoView({
        behavior: 'smooth'
      });
    });
  });

  // Fade in on scroll
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.fade-in').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s, transform 0.6s';
    observer.observe(el);
  });
});
</script>
```

**Aplicar em elementos:**
```html
<div class="fade-in">
  <!-- Conteúdo que aparece ao scroll -->
</div>
```

---

## 📱 RESPONSIVIDADE

### Breakpoints Tailwind

```
sm:  640px
md:  768px
lg:  1024px
xl:  1280px
```

### Mobile (< 640px)

- 1 coluna em todos os grids
- Padding reduzido: `px-4`
- Fonte menor: `text-4xl` para títulos
- Menu hamburguer (opcional)

### Tablet (640px - 1024px)

- 2 colunas onde apropriado
- Padding: `px-6`
- Fonte média

### Desktop (> 1024px)

- 3 colunas
- Padding: `px-8`
- Fonte completa

---

## 📄 TEMPLATE HTML BASE

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NEXUS - Plataforma Unificada de Automação</title>
  <meta name="description" content="Plataforma de agentes de IA para automação de processos empresariais">
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: 'Inter', sans-serif;
    }
  </style>
</head>
<body class="bg-white">
  
  <!-- NAVBAR -->
  
  <!-- HERO SECTION -->
  
  <!-- SOCIAL PROOF -->
  
  <!-- BENEFÍCIOS -->
  
  <!-- AGENTES -->
  
  <!-- COMO FUNCIONA -->
  
  <!-- DEPOIMENTOS -->
  
  <!-- CTA FINAL -->
  
  <!-- FOOTER -->
  
  <script>
    // Scripts de animação aqui
  </script>
  
</body>
</html>
```

---

## ✅ CHECKLIST FINAL

- [ ] Todos os containers usam `max-w-7xl mx-auto`
- [ ] Padding horizontal consistente: `px-4 sm:px-6 lg:px-8`
- [ ] Gaps uniformes: `gap-6` ou `gap-8`
- [ ] Cards com altura equilibrada visualmente
- [ ] Cores seguem paleta definida
- [ ] Gradientes aplicados corretamente
- [ ] Tipografia hierárquica
- [ ] Responsivo em 3 breakpoints (mobile, tablet, desktop)
- [ ] Animações suaves
- [ ] Botões e links com hover effects
- [ ] SVGs inline para ícones de check
- [ ] Código limpo e comentado
- [ ] Meta tags corretas
- [ ] Google Fonts carregada
- [ ] Tailwind CDN funcionando
- [ ] Todos os links apontam para `http://127.0.0.1:5173/agents`

---

## 🚀 COMO USAR COM GITHUB COPILOT

1. **Copie este prompt inteiro**
2. **Abra seu IDE (VS Code)**
3. **Ative o GitHub Copilot** (Ctrl+I no VS Code)
4. **Cole este prompt**
5. **Pressione Enter** e deixe o Copilot gerar o HTML

O Copilot irá:
- ✅ Preencher placeholders com dados reais do NEXUS
- ✅ Gerar HTML semântico e válido
- ✅ Aplicar todas as classes Tailwind corretamente
- ✅ Incluir animações e interatividade
- ✅ Seguir a hierarquia de design

---

## 📌 NOTAS IMPORTANTES

1. **Este prompt é um guia completo** - Não deixe nada de fora
2. **Contexto é fundamental** - Copilot será mais preciso com detalhes
3. **Revise a saída** - Sempre verifique se as cores e estrutura estão corretas
4. **Teste responsividade** - Use DevTools para testar em 3 tamanhos
5. **Preserve os placeholders** - Se quiser gerar apenas uma seção, deixe claros os placeholders

---

**Criado em:** 6 de janeiro de 2026  
**Versão:** 1.0  
**Formato:** Markdown + HTML Templates
