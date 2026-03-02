# PROMPT PARA REDESIGN DO HEADER NEXUS

**Área:** Navbar + Hero Section "Agentes de IA"  
**⚠️ NÃO ALTERAR:** Botões dos agentes (já aprovados)

---

## ÁREA A SER MODIFICADA

Somente estas seções:
1. **Navbar superior** (NEXUS + Plataforma Unificada + botões Agentes/Diagnósticos/Fila)
2. **Hero Section** (🤖 Agentes de IA + subtítulo)

---

## SEÇÃO 1: NAVBAR SUPERIOR

**Psicologia:** Profissionalismo, estabilidade, confiança (azul escuro predominante)

### Background
```css
background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%);
/* from-slate-900 via-slate-800 to-slate-900 */
```

**Cores Hex Exatas:**
- Background início: `#0F172A` (slate-900)
- Background meio: `#1E293B` (slate-800)
- Background fim: `#0F172A` (slate-900)

### Especificações
- **Border Bottom:** `border-bottom: 1px solid rgba(148, 163, 184, 0.2);`
- **Altura:** h-20 (80px)
- **Padding:** px-6 lg:px-8
- **Sombra:** shadow-lg shadow-slate-900/50

### Estrutura HTML

```html
<nav class="sticky top-0 z-50 h-20 
            bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900
            border-b border-slate-400/20
            shadow-lg shadow-slate-900/50
            backdrop-blur-sm">
  
  <div class="max-w-7xl mx-auto px-6 lg:px-8 h-full">
    <div class="flex items-center justify-between h-full">
      
      <!-- LOGO E TÍTULO -->
      <div class="flex items-center space-x-3">
        
        <!-- Logo (Gradiente Azul-Roxo) -->
        <div class="w-12 h-12 rounded-xl 
                    bg-gradient-to-br from-blue-500 via-purple-500 to-cyan-500
                    flex items-center justify-center
                    shadow-lg shadow-blue-500/30
                    ring-2 ring-white/10">
          <span class="text-white font-black text-xl">N</span>
        </div>

        <!-- Textos -->
        <div class="flex flex-col">
          <h1 class="text-2xl font-black text-white tracking-tight">
            NEXUS
          </h1>
          <p class="text-sm text-slate-400 font-medium">
            Plataforma Unificada de Automação
          </p>
        </div>

      </div>

      <!-- BOTÕES DE NAVEGAÇÃO -->
      <div class="flex items-center space-x-3">
        
        <!-- Botão: Agentes (ATIVO - Azul) -->
        <button class="px-5 py-2.5 rounded-lg font-semibold text-sm
                       bg-gradient-to-r from-blue-600 to-blue-700
                       text-white
                       shadow-md shadow-blue-500/30
                       hover:shadow-lg hover:shadow-blue-500/40
                       hover:scale-105
                       transition-all duration-300
                       ring-2 ring-blue-400/20">
          🤖 Agentes
        </button>

        <!-- Botão: Diagnósticos (INATIVO - Transparente) -->
        <button class="px-5 py-2.5 rounded-lg font-semibold text-sm
                       bg-slate-800/50
                       text-slate-300
                       border border-slate-700/50
                       hover:bg-slate-700/50
                       hover:text-white
                       hover:border-slate-600
                       hover:scale-105
                       transition-all duration-300">
          🔍 Diagnósticos
        </button>

        <!-- Botão: Fila (INATIVO - Transparente) -->
        <button class="px-5 py-2.5 rounded-lg font-semibold text-sm
                       bg-slate-800/50
                       text-slate-300
                       border border-slate-700/50
                       hover:bg-slate-700/50
                       hover:text-white
                       hover:border-slate-600
                       hover:scale-105
                       transition-all duration-300">
          📊 Fila
        </button>

      </div>

    </div>
  </div>

</nav>
```

### Detalhamento dos Elementos

**1. Logo "N":**
- Tamanho: w-12 h-12 (48x48px)
- Gradiente: from-blue-500 via-purple-500 to-cyan-500
- Sombra: shadow-lg shadow-blue-500/30
- Ring: ring-2 ring-white/10
- Border radius: rounded-xl

**2. Título "NEXUS":**
- Font: text-2xl font-black
- Cor: text-white
- Tracking: tracking-tight

**3. Subtítulo:**
- Font: text-sm font-medium
- Cor: text-slate-400

**4. Botão ATIVO (Agentes):**
- Gradiente: from-blue-600 to-blue-700
- Sombra: shadow-md shadow-blue-500/30
- Hover: shadow-lg shadow-blue-500/40
- Ring: ring-2 ring-blue-400/20

**5. Botões INATIVOS:**
- Background: bg-slate-800/50
- Border: border-slate-700/50
- Hover: bg-slate-700/50 + text-white

---

## SEÇÃO 2: HERO SECTION "AGENTES DE IA"

**Psicologia:** Inovação, tecnologia, sofisticação (roxo-azul)

### Background
```css
background: linear-gradient(135deg, #1E3A8A 0%, #312E81 50%, #155E75 100%);
/* from-blue-900 via-indigo-900 to-cyan-800 */
```

**Cores Hex Exatas:**
- Início: `#1E3A8A` (blue-900)
- Meio: `#312E81` (indigo-900)
- Fim: `#155E75` (cyan-800)

### Especificações
- **Padding:** py-12 lg:py-16
- **Margin:** mx-6 lg:mx-8 mt-8
- **Border radius:** rounded-2xl
- **Sombra:** shadow-2xl shadow-blue-900/30

### Estrutura HTML

```html
<div class="mx-6 lg:mx-8 mt-8 mb-8">
  
  <div class="rounded-2xl overflow-hidden
              bg-gradient-to-br from-blue-900 via-indigo-900 to-cyan-800
              shadow-2xl shadow-blue-900/30
              border border-blue-700/20
              relative">
    
    <!-- Padrão de fundo decorativo -->
    <div class="absolute inset-0 opacity-5">
      <div class="absolute top-0 right-0 w-96 h-96 bg-blue-400 rounded-full blur-3xl"></div>
      <div class="absolute bottom-0 left-0 w-96 h-96 bg-purple-400 rounded-full blur-3xl"></div>
    </div>

    <!-- Conteúdo -->
    <div class="relative py-12 lg:py-16 px-8 lg:px-12">
      
      <div class="max-w-4xl">
        
        <!-- Título com Gradiente -->
        <h2 class="text-4xl lg:text-5xl font-black mb-4 leading-tight">
          <span class="bg-gradient-to-r from-blue-300 via-purple-300 to-cyan-300 
                       bg-clip-text text-transparent
                       drop-shadow-lg">
            🤖 Agentes de IA
          </span>
        </h2>

        <!-- Subtítulo -->
        <p class="text-lg lg:text-xl text-blue-100 font-medium leading-relaxed">
          Automações inteligentes para MEI e pequenos negócios
        </p>

        <!-- Badge decorativo -->
        <div class="mt-6 inline-flex items-center space-x-2 
                    px-4 py-2 rounded-full
                    bg-white/10 backdrop-blur-sm
                    border border-white/20">
          <span class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
          <span class="text-sm text-blue-100 font-semibold">
            6 Agentes Disponíveis
          </span>
        </div>

      </div>

    </div>

  </div>

</div>
```

### Detalhamento dos Elementos

**1. Container Principal:**
- Border radius: rounded-2xl
- Sombra: shadow-2xl shadow-blue-900/30
- Border: border-blue-700/20
- Position: relative

**2. Padrão Decorativo:**
- Dois círculos blur gigantes
- Opacidade: opacity-5
- Cores: bg-blue-400 e bg-purple-400
- Blur: blur-3xl

**3. Título "🤖 Agentes de IA":**
- Font: text-4xl lg:text-5xl font-black
- Gradiente: from-blue-300 via-purple-300 to-cyan-300
- Clip: bg-clip-text text-transparent
- Drop shadow: drop-shadow-lg

**4. Subtítulo:**
- Font: text-lg lg:text-xl font-medium
- Cor: text-blue-100
- Leading: leading-relaxed

**5. Badge "6 Agentes Disponíveis":**
- Background: bg-white/10 backdrop-blur-sm
- Border: border-white/20
- Indicador: w-2 h-2 bg-green-400 animate-pulse
- Font: text-sm font-semibold

---

## CORES DE REFERÊNCIA (HEX)

### NAVBAR
- Background escuro: `#0F172A`, `#1E293B` (slate-900, slate-800)
- Logo gradiente: `#3B82F6`, `#8B5CF6`, `#06B6D4` (blue-500, purple-500, cyan-500)
- Botão ativo: `#2563EB`, `#1E40AF` (blue-600, blue-700)
- Texto inativo: `#CBD5E1` (slate-300)

### HERO SECTION
- Background: `#1E3A8A`, `#312E81`, `#155E75` (blue-900, indigo-900, cyan-800)
- Título gradiente: `#93C5FD`, `#D8B4FE`, `#67E8F9` (blue-300, purple-300, cyan-300)
- Subtítulo: `#DBEAFE` (blue-100)
- Badge background: `rgba(255, 255, 255, 0.1)`
- Indicador: `#4ADE80` (green-400)

---

## RESPONSIVIDADE

### MOBILE (< 768px)
- Navbar: h-16, px-4
- Logo: w-10 h-10
- Título: text-xl
- Hero: mx-4 mt-4, py-8 px-6
- Título hero: text-3xl

### TABLET (768px - 1024px)
- Navbar: h-18, px-6
- Hero: py-10, px-8
- Título: text-4xl

### DESKTOP (> 1024px)
- Navbar: h-20, px-8
- Hero: py-16, px-12
- Título: text-5xl

---

## ESTADOS INTERATIVOS

**1. Botão ATIVO (Agentes):**
- Normal: Gradiente azul + sombra azul
- Hover: Escala 105% + sombra mais intensa
- Active: Escala 98%
- Focus: Ring azul

**2. Botões INATIVOS:**
- Normal: Transparente + border cinza
- Hover: Background mais claro + texto branco
- Active: Escala 98%
- Focus: Ring cinza

**3. Logo "N":**
- Hover: Rotação suave 5deg
- Transition: 300ms

**4. Badge "6 Agentes":**
- Indicador verde: Pulse infinito
- Hover container: Leve brilho

---

## CHECKLIST

### NAVBAR
✅ Background gradiente escuro (slate-900/800)  
✅ Logo com gradiente azul-roxo-cyan + sombra  
✅ Título "NEXUS" branco, bold  
✅ Subtítulo cinza claro  
✅ Botão ativo (Agentes) azul com gradiente  
✅ Botões inativos transparentes + hover  
✅ Sticky no topo (z-50)  
✅ Sombra inferior suave  

### HERO SECTION
✅ Background gradiente azul-indigo-cyan  
✅ Título com gradiente claro no texto  
✅ Emoji 🤖 integrado ao título  
✅ Subtítulo azul claro  
✅ Badge "6 Agentes" com indicador pulse  
✅ Padrão decorativo de fundo sutil  
✅ Border radius arredondado  
✅ Sombra dramática azul  

### ⚠️ NÃO ALTERADO
✅ Botões "Executar" dos agentes mantidos  
✅ Cores dos cards mantidas  
✅ Grid de agentes intacto  

---

## RESULTADO ESPERADO

**NAVBAR:**
- Fundo escuro profissional (slate-900/800)
- Logo colorido destaque (azul-roxo-cyan)
- Botão "Agentes" ativo com gradiente azul vibrante
- Outros botões sutis mas visíveis
- Visual premium e moderno

**HERO:**
- Fundo rico em azul-indigo-cyan (noite tecnológica)
- Título com gradiente claro brilhante
- Efeito de profundidade com padrão sutil
- Badge animado transmite atividade
- Conexão visual com botões dos agentes (tons azuis)

**CONJUNTO:**
- Navbar escuro ancora confiança
- Hero vibrante gera interesse
- Transição suave entre seções
- Cores conectadas psicologicamente
- Hierarquia visual clara
