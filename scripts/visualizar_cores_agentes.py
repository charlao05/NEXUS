"""
🎨 VISUALIZAÇÃO DAS CORES DOS AGENTES NEXUS
Demonstração das cores psicológicas únicas de cada agente
"""

def print_color_samples():
    """
    Imprime amostras visuais das cores de cada agente
    """
    print("\n" + "=" * 80)
    print("🎨 CORES DOS AGENTES NEXUS - Gradientes Psicológicos Únicos".center(80))
    print("=" * 80 + "\n")

    agents = [
        {
            'emoji': '🌐',
            'name': 'Automação Web',
            'agent_id': 'site_agent',
            'color': 'AZUL',
            'gradient_start': '#2563EB',
            'gradient_end': '#1E40AF',
            'psychology': 'Confiança técnica, estabilidade, profissionalismo',
            'css_class': '.btn-automation'
        },
        {
            'emoji': '📅',
            'name': 'Agenda Completa',
            'agent_id': 'agenda_agent',
            'color': 'ROXO',
            'gradient_start': '#7C3AED',
            'gradient_end': '#6D28D9',
            'psychology': 'Organização, inteligência, sofisticação',
            'css_class': '.btn-agenda'
        },
        {
            'emoji': '👥',
            'name': 'Clientes (CRM)',
            'agent_id': 'clients_agent',
            'color': 'CYAN',
            'gradient_start': '#0891B2',
            'gradient_end': '#0E7490',
            'psychology': 'Relacionamento, comunicação, confiança social',
            'css_class': '.btn-clients'
        },
        {
            'emoji': '💰',
            'name': 'Análise Financeira',
            'agent_id': 'finance_agent',
            'color': 'VERDE',
            'gradient_start': '#059669',
            'gradient_end': '#047857',
            'psychology': 'Crescimento, dinheiro, segurança financeira',
            'css_class': '.btn-financial'
        },
        {
            'emoji': '📄',
            'name': 'Nota Fiscal',
            'agent_id': 'nf_agent',
            'color': 'INDIGO',
            'gradient_start': '#4F46E5',
            'gradient_end': '#4338CA',
            'psychology': 'Profissionalismo, seriedade, documentação',
            'css_class': '.btn-invoice'
        },
        {
            'emoji': '💳',
            'name': 'Cobranças',
            'agent_id': 'collections_agent',
            'color': 'ROSA',
            'gradient_start': '#DB2777',
            'gradient_end': '#BE185D',
            'psychology': 'Ação urgente (mas suave), importância, atenção',
            'css_class': '.btn-billing'
        }
    ]

    for i, agent in enumerate(agents, 1):
        print(f"{i}. {agent['emoji']} {agent['name']}")
        print(f"   ID: {agent['agent_id']}")
        print(f"   Cor: {agent['color']}")
        print(f"   Gradiente: {agent['gradient_start']} → {agent['gradient_end']}")
        print(f"   Psicologia: {agent['psychology']}")
        print(f"   CSS Class: {agent['css_class']}")
        print()

    print("=" * 80)
    print("\n✅ Cada agente possui identidade visual única!")
    print("✅ Cores baseadas em psicologia para melhor UX!")
    print("✅ Usuário reconhece agente instantaneamente pela cor!\n")


def generate_css_classes():
    """
    Gera as classes CSS completas para cada agente
    """
    print("\n" + "=" * 80)
    print("📝 CLASSES CSS GERADAS".center(80))
    print("=" * 80 + "\n")

    agents_css = {
        'btn-automation': {
            'normal': 'linear-gradient(135deg, #2563EB 0%, #1E40AF 100%)',
            'hover': 'linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%)',
            'shadow': 'rgba(37, 99, 235, 0.24)',
            'ring': 'rgba(147, 197, 253, 0.5)'
        },
        'btn-agenda': {
            'normal': 'linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%)',
            'hover': 'linear-gradient(135deg, #6D28D9 0%, #5B21B6 100%)',
            'shadow': 'rgba(124, 58, 237, 0.24)',
            'ring': 'rgba(216, 180, 254, 0.5)'
        },
        'btn-clients': {
            'normal': 'linear-gradient(135deg, #0891B2 0%, #0E7490 100%)',
            'hover': 'linear-gradient(135deg, #0E7490 0%, #155E75 100%)',
            'shadow': 'rgba(8, 145, 178, 0.24)',
            'ring': 'rgba(103, 232, 249, 0.5)'
        },
        'btn-financial': {
            'normal': 'linear-gradient(135deg, #059669 0%, #047857 100%)',
            'hover': 'linear-gradient(135deg, #047857 0%, #065F46 100%)',
            'shadow': 'rgba(5, 150, 105, 0.24)',
            'ring': 'rgba(134, 239, 172, 0.5)'
        },
        'btn-invoice': {
            'normal': 'linear-gradient(135deg, #4F46E5 0%, #4338CA 100%)',
            'hover': 'linear-gradient(135deg, #4338CA 0%, #3730A3 100%)',
            'shadow': 'rgba(79, 70, 229, 0.24)',
            'ring': 'rgba(165, 180, 252, 0.5)'
        },
        'btn-billing': {
            'normal': 'linear-gradient(135deg, #DB2777 0%, #BE185D 100%)',
            'hover': 'linear-gradient(135deg, #BE185D 0%, #9F1239 100%)',
            'shadow': 'rgba(219, 39, 119, 0.24)',
            'ring': 'rgba(249, 168, 212, 0.5)'
        }
    }

    for class_name, styles in agents_css.items():
        print(f"/* {class_name.upper()} */")
        print(f".{class_name} {{")
        print(f"  background: {styles['normal']};")
        print(f"  box-shadow: 0 12px 26px {styles['shadow']};")
        print("}")
        print()
        print(f".{class_name}:hover {{")
        print(f"  background: {styles['hover']};")
        print(f"  box-shadow: 0 20px 25px -5px {styles['shadow'].replace('0.24', '0.4')},")
        print(f"              0 10px 10px -5px {styles['shadow'].replace('0.24', '0.2')};")
        print("  transform: translateY(-1px) scale(1.02);")
        print("}")
        print()
        print(f".{class_name}:focus {{")
        print(f"  box-shadow: 0 0 0 4px {styles['ring']};")
        print("}")
        print()
        print("-" * 80)
        print()

    print("=" * 80 + "\n")


def generate_typescript_map():
    """
    Gera o mapeamento TypeScript para uso no React
    """
    print("\n" + "=" * 80)
    print("⚛️  MAPEAMENTO TYPESCRIPT/REACT".center(80))
    print("=" * 80 + "\n")

    print("// Mapa de classes CSS para cada tipo de agente")
    print("const getAgentButtonClass = (agentName: string): string => {")
    print("  const classMap: Record<string, string> = {")
    print("    'site_agent': 'btn-automation',       // 🌐 Azul - Confiança técnica")
    print("    'agenda_agent': 'btn-agenda',         // 📅 Roxo - Organização")
    print("    'clients_agent': 'btn-clients',       // 👥 Cyan - Relacionamento")
    print("    'finance_agent': 'btn-financial',     // 💰 Verde - Crescimento")
    print("    'nf_agent': 'btn-invoice',            // 📄 Indigo - Profissionalismo")
    print("    'collections_agent': 'btn-billing'    // 💳 Rosa - Urgência suave")
    print("  }")
    print("  return classMap[agentName] || 'btn-execute'")
    print("}")
    print()
    print("// Uso no componente:")
    print("const buttonClass = `agent-card__button ${getAgentButtonClass(agent.name)}`")
    print()
    print("=" * 80 + "\n")


if __name__ == "__main__":
    print_color_samples()
    generate_css_classes()
    generate_typescript_map()

    print("\n" + "🎨" * 40)
    print("\n✨ IMPLEMENTAÇÃO COMPLETA!")
    print("\n📁 Arquivos criados:")
    print("   ✅ docs/PROMPT_BOTOES_GRADIENTES.md - Prompt completo")
    print("   ✅ docs/CORES_AGENTES_PSICOLOGIA.md - Guia de cores")
    print("   ✅ frontend/src/pages/AgentsPage.tsx - Lógica React atualizada")
    print("   ✅ frontend/src/pages/AgentsPage.css - Estilos com gradientes únicos")
    print("\n🚀 Reinicie o frontend para ver as cores!")
    print("   npm run dev\n")
    print("🎨" * 40 + "\n")
