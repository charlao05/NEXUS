"""
Script para gerar Landing Page do NEXUS usando IA
Autor: Sistema NEXUS
Data: 2026-01-06
"""

# Prompt completo para a IA
prompt_landing_page = """
Crie uma landing page HTML completa, moderna e profissional para NEXUS - Plataforma Unificada de Automação.

=== DIRETRIZES IMPORTANTES ===

LEGAL E ÉTICO:
- NÃO prometa valores específicos de economia (ex: "economize R$ 3.000")
- NÃO prometa resultados garantidos (ex: "aumente vendas em 40%")
- Use linguagem de POTENCIAL, não de garantia
- Foque em FUNCIONALIDADES, não em promessas financeiras

CONTEÚDO:
- Descreva o que cada agente FAZ (funcionalidades)
- Explique COMO funciona
- Mencione PARA QUÊ serve
- Use linguagem profissional mas acessível

=== ESPECIFICAÇÕES TÉCNICAS ===

TECNOLOGIA:
- HTML5 semântico
- Tailwind CSS via CDN: https://cdn.tailwindcss.com
- JavaScript vanilla (sem dependências externas)
- Arquivo único completo e funcional
- 100% responsivo

PALETA DE CORES:

Cores Principais:
- Primária: #3B82F6 (blue-500)
- Primária Escura: #2563EB (blue-600)
- Secundária: #8B5CF6 (purple-500)
- Secundária Escura: #7C3AED (purple-600)
- Accent: #06B6D4 (cyan-500)

Backgrounds:
- Principal: #FFFFFF (white)
- Alternado: #F9FAFB (gray-50)

Textos:
- Principal: #1F2937 (gray-800)
- Secundário: #6B7280 (gray-500)
- Claro: #9CA3AF (gray-400)

Gradientes:
- Hero Background: from-blue-50 via-purple-50 to-cyan-50
- CTAs: from-blue-600 to-purple-600
- Footer: from-gray-800 to-gray-900

CORES POR AGENTE (Headers de Cards):
1. Automação Web: from-blue-500 to-blue-600
2. Agenda Completa: from-purple-500 to-purple-600
3. Clientes (CRM): from-cyan-500 to-cyan-600
4. Análise Financeira: from-green-500 to-green-600
5. Nota Fiscal: from-indigo-500 to-indigo-600
6. Cobranças: from-pink-500 to-pink-600

=== ESTRUTURA COMPLETA ===

<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NEXUS - Plataforma Unificada de Automação</title>
  <meta name="description" content="Plataforma profissional de agentes de IA para automação de processos empresariais">
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Inter', sans-serif; }
  </style>
</head>
<body class="bg-white">

=== SEÇÃO 1: NAVBAR ===

Especificações:
- Fixo no topo: fixed top-0 w-full z-50
- Background semi-transparente: bg-white/90 backdrop-blur-md
- Altura: h-16
- Sombra sutil: shadow-sm
- Container: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8

Layout interno:
- Flex: justify-between items-center
- Logo à esquerda (gradiente azul-roxo)
- Menu centro (esconder em mobile: hidden md:flex)
- CTA à direita

Links do menu:
- Agentes
- Benefícios  
- Como Funciona
- Contato

CTA Button:
- Classes: bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-2 rounded-lg font-semibold hover:shadow-lg transition
- Link: http://127.0.0.1:5173/agents

=== SEÇÃO 2: HERO ===

Especificações:
- Padding: pt-32 pb-16 lg:pt-40 lg:pb-24
- Background: bg-gradient-to-br from-blue-50 via-purple-50 to-cyan-50
- Container: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8
- Conteúdo: text-center max-w-4xl mx-auto

Elementos:

H1:
- Classes: text-5xl lg:text-6xl font-bold text-gray-900 mb-6 leading-tight
- Texto sugerido: "Automatize Seu Negócio com Inteligência Artificial"
- Destaque "Inteligência Artificial" com gradiente: bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent

Subtítulo:
- Classes: text-xl lg:text-2xl text-gray-600 mb-8 leading-relaxed
- Descrever: Plataforma de agentes de IA para MEI e pequenas empresas

CTAs Container:
- Classes: flex flex-col sm:flex-row gap-4 justify-center mb-8

CTA Primário:
- Classes: bg-gradient-to-r from-blue-600 to-purple-600 text-white px-8 py-4 rounded-lg font-semibold text-lg hover:shadow-2xl hover:scale-105 transition-all
- Texto: "Acessar Plataforma"
- Link: http://127.0.0.1:5173/agents

CTA Secundário:
- Classes: bg-white border-2 border-blue-600 text-blue-600 px-8 py-4 rounded-lg font-semibold text-lg hover:bg-blue-50 transition
- Texto: "Ver Demonstração"
- Link: #agentes (scroll suave)

Features badges (abaixo dos CTAs):
- Container: flex flex-col sm:flex-row items-center justify-center gap-6 text-sm text-gray-600
- 3 itens com ícone check verde SVG + texto
- Textos sugeridos: "Configuração rápida" | "Suporte especializado" | "Interface intuitiva"

=== SEÇÃO 3: SOCIAL PROOF ===

Especificações:
- Classes: py-12 bg-white border-b
- Container: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8

Layout:
- Texto introdutório centralizado: text-center text-gray-600 mb-8
- Grid: grid-cols-1 md:grid-cols-3 gap-8 text-center

Cada card:
- Número grande: text-4xl font-bold (cor variada: blue-600, purple-600, green-600)
- Label: text-gray-600

Sugestões de métricas (CONSERVADORAS):
- "500+" → "Usuários Ativos"
- "6" → "Agentes Disponíveis"
- "24/7" → "Disponibilidade"

=== SEÇÃO 4: BENEFÍCIOS ===

Especificações:
- Classes: py-16 lg:py-24 bg-gray-50
- Container: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8

Título:
- Classes: text-3xl lg:text-4xl font-bold text-center mb-4 text-gray-900
- Texto: "Por Que Escolher o NEXUS?"

Subtítulo:
- Classes: text-xl text-gray-600 text-center mb-12 max-w-3xl mx-auto
- Descrever benefícios gerais da automação

Grid:
- Classes: grid grid-cols-1 md:grid-cols-3 gap-8

Cada Card de Benefício:
- Container: bg-white rounded-xl shadow-lg p-8 hover:shadow-2xl transition-all min-h-[280px]
- Ícone emoji: text-5xl mb-4
- Título: text-2xl font-semibold mb-3 text-gray-900
- Descrição: text-gray-600 leading-relaxed

3 Benefícios (sugestões SEM promessas financeiras):

Card 1:
- Ícone: ⏱️
- Título: "Automação de Processos"
- Descrição: Foque em funcionalidade de automação de tarefas repetitivas

Card 2:
- Ícone: 🎯
- Título: "Organização Centralizada"
- Descrição: Todas as ferramentas em uma plataforma única

Card 3:
- Ícone: 📊
- Título: "Insights e Controle"
- Descrição: Visibilidade completa das operações do negócio

=== SEÇÃO 5: SHOWCASE DE AGENTES (PRINCIPAL) ===

Especificações:
- Classes: py-16 lg:py-24 bg-white
- Container: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8

Header:
- Div: text-center mb-12
- Título: text-3xl lg:text-4xl font-bold mb-4
- Subtítulo: text-xl text-gray-600

Grid de Agentes:
- Classes: grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8

ESTRUTURA DE CADA CARD (6 agentes):

Container:
- Classes: bg-white rounded-xl shadow-md hover:shadow-2xl transition-all duration-300 overflow-hidden group

Header do Card (colorido):
- Classes: bg-gradient-to-r [COR_ESPECÍFICA] p-6 text-white
- Flex top: flex items-start justify-between mb-3
- Ícone emoji: text-5xl
- Badge: bg-white/20 backdrop-blur-sm px-3 py-1 rounded-full text-xs font-semibold
- Título: text-xl font-bold

Body do Card:
- Classes: p-6

Descrição:
- Classes: text-gray-600 leading-relaxed mb-6
- Descrever funcionalidades REAIS do agente

Lista de Features:
- Container: ul space-y-2 mb-6
- Cada item (3-4 features):
```html
  <li class="flex items-start text-sm text-gray-600">
    <svg class="w-5 h-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
    </svg>
    [Funcionalidade específica]
  </li>
```

Botão de Ação:
- Classes: w-full bg-gradient-to-r [MESMA_COR_DO_HEADER] text-white font-semibold py-3 rounded-lg hover:shadow-lg hover:scale-105 transition-all duration-300
- Texto: "Executar Agente"

AGENTE 1 - Automação Web:
- Cor: from-blue-500 to-blue-600
- Ícone: 🌐
- Badge: Funcionalidade principal (ex: "Playwright")
- Descrever: Automação de navegação web, formulários, login
- Features: Listar capacidades reais do agente

AGENTE 2 - Agenda Completa:
- Cor: from-purple-500 to-purple-600
- Ícone: 📅
- Badge: Funcionalidade principal (ex: "Lembretes")
- Descrever: Gestão de compromissos, prazos fiscais
- Features: Listar capacidades reais

AGENTE 3 - Clientes (CRM):
- Cor: from-cyan-500 to-cyan-600
- Ícone: 👥
- Badge: Funcionalidade principal (ex: "CRM")
- Descrever: Gestão completa de clientes
- Features: Listar capacidades reais

AGENTE 4 - Análise Financeira:
- Cor: from-green-500 to-green-600
- Ícone: 💰
- Badge: Funcionalidade principal (ex: "Relatórios")
- Descrever: Controle financeiro e análises
- Features: Listar capacidades reais

AGENTE 5 - Nota Fiscal:
- Cor: from-indigo-500 to-indigo-600
- Ícone: 📄
- Badge: Funcionalidade principal (ex: "NFS-e")
- Descrever: Suporte para emissão de notas
- Features: Listar capacidades reais

AGENTE 6 - Cobranças:
- Cor: from-pink-500 to-pink-600
- Ícone: 💳
- Badge: Funcionalidade principal (ex: "Automático")
- Descrever: Gestão de cobranças
- Features: Listar capacidades reais

=== SEÇÃO 6: COMO FUNCIONA ===

Especificações:
- Classes: py-16 lg:py-24 bg-gray-50
- Container: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8

Título:
- Classes: text-3xl lg:text-4xl font-bold text-center mb-16
- Texto: "Como Funciona"

Grid:
- Classes: grid grid-cols-1 md:grid-cols-3 gap-12

Cada Passo (3 passos):

Container: text-center

Número:
- Classes: w-16 h-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full flex items-center justify-center text-white text-2xl font-bold mx-auto mb-4
- Conteúdo: 1, 2, 3

Título Passo:
- Classes: text-xl font-semibold mb-3
- Exemplos: "Escolha os Agentes" | "Configure Parâmetros" | "Execute e Monitore"

Descrição:
- Classes: text-gray-600
- Explicar o passo brevemente

=== SEÇÃO 7: DEPOIMENTOS ===

Especificações:
- Classes: py-16 lg:py-24 bg-white
- Container: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8

Título:
- Classes: text-3xl lg:text-4xl font-bold text-center mb-12

Grid:
- Classes: grid grid-cols-1 md:grid-cols-3 gap-8

Cada Depoimento:

Container:
- Classes: bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl p-6 shadow-lg

Header (pessoa):
- Classes: flex items-center mb-4
- Avatar: w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center text-white font-bold mr-3
- Nome: font-semibold
- Cargo: text-sm text-gray-600

Depoimento:
- Classes: text-gray-700 italic
- Usar aspas: "[Depoimento focado em FUNCIONALIDADE, não em resultados financeiros]"

3 Depoimentos (focar em usabilidade, não em ROI):
- Depoimento 1: Fácil de usar
- Depoimento 2: Suporte excelente
- Depoimento 3: Funcionalidades úteis

=== SEÇÃO 8: CTA FINAL ===

Especificações:
- Classes: py-16 lg:py-24 bg-gradient-to-r from-blue-600 to-purple-600
- Container: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center

Título:
- Classes: text-3xl lg:text-4xl font-bold text-white mb-4
- Texto: Call to action forte

Subtítulo:
- Classes: text-xl text-blue-100 mb-8 max-w-2xl mx-auto

CTA Button:
- Classes: inline-block bg-white text-blue-600 px-8 py-4 rounded-lg font-semibold text-lg hover:shadow-2xl hover:scale-105 transition-all
- Texto: "Acessar Plataforma"
- Link: http://127.0.0.1:5173/agents

Features (abaixo do botão):
- Classes: flex flex-col sm:flex-row items-center justify-center gap-6 text-blue-100 text-sm mt-6
- 3 itens com checkmark: "✓ [Feature]"

=== SEÇÃO 9: FOOTER ===

Especificações:
- Classes: bg-gray-900 text-gray-400 py-12
- Container: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8

Layout: text-center

Logo:
- Classes: text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-4
- Texto: NEXUS

Tagline:
- Classes: mb-4
- Texto: Descrição curta da plataforma

Links:
- Classes: flex justify-center space-x-6 mb-6
- Links: Agentes | Benefícios | Contato | Termos | Privacidade
- Hover: hover:text-white transition

Copyright:
- Classes: text-sm
- Texto: © 2026 NEXUS. Todos os direitos reservados.

=== JAVASCRIPT (Scroll Suave + Animações) ===

Adicionar antes de </body>:
```javascript
<script>
document.addEventListener('DOMContentLoaded', function() {
  // Smooth scroll para links internos
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    });
  });

  // Fade in ao scroll
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };
  
  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, observerOptions);
  
  // Aplicar animação aos cards e seções
  const animatedElements = document.querySelectorAll('.animate-on-scroll');
  animatedElements.forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
  });
});
</script>
```

Adicionar classe "animate-on-scroll" aos elementos que devem ter fade-in:
- Cards de benefícios
- Cards de agentes
- Cards de depoimentos
- Passos do "Como Funciona"

=== RESPONSIVIDADE ===

Mobile (< 640px):
- Menu: Hidden, mostrar botão hamburguer (opcional)
- Grid: 1 coluna (grid-cols-1)
- Fonte: reduzida (text-4xl para hero)
- Padding: px-4
- CTAs: flex-col (empilhados)

Tablet (640px - 1024px):
- Grid: 2 colunas onde apropriado (md:grid-cols-2)
- Fonte: média
- Padding: sm:px-6

Desktop (> 1024px):
- Grid: 3 colunas (lg:grid-cols-3)
- Fonte: completa
- Padding: lg:px-8
- Menu: completo horizontal

=== REQUISITOS FINAIS ===

✅ Arquivo HTML único completo
✅ Tailwind CSS via CDN
✅ JavaScript inline para interações
✅ Todas as cores da paleta aplicadas
✅ Grid system consistente (max-w-7xl)
✅ Padding uniforme (px-4 sm:px-6 lg:px-8)
✅ Gaps consistentes (gap-6 ou gap-8)
✅ Tipografia hierárquica
✅ Animações suaves
✅ 100% responsivo
✅ SVGs inline para ícones
✅ Links funcionais para http://127.0.0.1:5173/agents
✅ Código limpo e bem comentado
✅ SEM promessas de resultados financeiros
✅ Foco em FUNCIONALIDADES reais

=== OBSERVAÇÃO CRÍTICA ===

O conteúdo (textos, descrições dos agentes, funcionalidades) deve:
- Ser baseado nas capacidades REAIS dos agentes
- Evitar promessas de resultados
- Focar em "o que faz" e "para que serve"
- Usar linguagem profissional mas acessível
- Ser honesto sobre limitações quando relevante

Gere o código HTML completo seguindo TODAS estas especificações.
"""

# Função para salvar o prompt em arquivo
def salvar_prompt(filename="prompt_landing_page.txt"):
    """Salva o prompt em arquivo de texto"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(prompt_landing_page)
    print(f"✅ Prompt salvo em: {filename}")

# Função para usar com API de IA (exemplo com OpenAI)
def gerar_landing_page_openai(api_key=None):
    """
    Gera a landing page usando OpenAI
    Instale: pip install openai
    """
    try:
        from openai import OpenAI
        
        if not api_key:
            print("⚠️  Configure sua API key da OpenAI")
            return
        
        client = OpenAI(api_key=api_key)
        
        print("🤖 Gerando landing page com IA...")
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "Você é um expert em desenvolvimento web, design de interfaces e HTML/CSS/JavaScript. Crie código limpo, profissional e funcional."
                },
                {
                    "role": "user",
                    "content": prompt_landing_page
                }
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        html_code = response.choices[0].message.content
        
        # Salvar HTML gerado
        with open('landing_page_nexus.html', 'w', encoding='utf-8') as f:
            f.write(html_code)
        
        print("✅ Landing page gerada: landing_page_nexus.html")
        return html_code
        
    except ImportError:
        print("❌ Instale a biblioteca: pip install openai")
    except Exception as e:
        print(f"❌ Erro: {e}")

# Função para usar com Anthropic Claude
def gerar_landing_page_claude(api_key=None):
    """
    Gera a landing page usando Anthropic Claude
    Instale: pip install anthropic
    """
    try:
        import anthropic
        
        if not api_key:
            print("⚠️  Configure sua API key da Anthropic")
            return
        
        client = anthropic.Anthropic(api_key=api_key)
        
        print("🤖 Gerando landing page com Claude...")
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": prompt_landing_page
                }
            ]
        )
        
        html_code = message.content[0].text
        
        # Salvar HTML gerado
        with open('landing_page_nexus.html', 'w', encoding='utf-8') as f:
            f.write(html_code)
        
        print("✅ Landing page gerada: landing_page_nexus.html")
        return html_code
        
    except ImportError:
        print("❌ Instale a biblioteca: pip install anthropic")
    except Exception as e:
        print(f"❌ Erro: {e}")

# Função para copiar prompt para clipboard
def copiar_prompt_para_clipboard():
    """Copia o prompt para a área de transferência"""
    try:
        import pyperclip
        pyperclip.copy(prompt_landing_page)
        print("✅ Prompt copiado para a área de transferência!")
        print("📋 Cole no chat da IA do VSCode")
    except ImportError:
        print("❌ Instale: pip install pyperclip")
        print("📋 Ou copie manualmente do arquivo prompt_landing_page.txt")

# Menu principal
def main():
    """Menu de opções"""
    print("\n" + "="*60)
    print("🚀 GERADOR DE LANDING PAGE NEXUS")
    print("="*60)
    print("\nEscolha uma opção:")
    print("\n1. Salvar prompt em arquivo")
    print("2. Copiar prompt para clipboard (colar no VSCode)")
    print("3. Gerar com OpenAI GPT-4")
    print("4. Gerar com Anthropic Claude")
    print("5. Mostrar prompt na tela")
    print("0. Sair")
    
    opcao = input("\n👉 Opção: ")
    
    if opcao == "1":
        salvar_prompt()
        print("\n💡 Dica: Use este arquivo com a IA do VSCode")
        
    elif opcao == "2":
        copiar_prompt_para_clipboard()
        
    elif opcao == "3":
        api_key = input("🔑 API Key OpenAI: ")
        gerar_landing_page_openai(api_key)
        
    elif opcao == "4":
        api_key = input("🔑 API Key Anthropic: ")
        gerar_landing_page_claude(api_key)
        
    elif opcao == "5":
        print("\n" + "="*60)
        print(prompt_landing_page)
        print("="*60)
        
    elif opcao == "0":
        print("\n👋 Até logo!")
        return
    
    else:
        print("\n❌ Opção inválida")
    
    # Perguntar se quer continuar
    if input("\n🔄 Executar outra ação? (s/n): ").lower() == 's':
        main()

# Executar
if __name__ == "__main__":
    main()
