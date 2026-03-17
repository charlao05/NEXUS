/**
 * Agents Page - NEXUS
 * Página de gerenciamento dos agentes de IA
 * Acesso baseado no plano freemium: free → 1 agente, essencial → 3, profissional+ → todos
 */

import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Users, DollarSign, Bot, Lock, Sparkles } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import { usePlanLimits } from '../hooks/usePlanLimits';

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: LucideIcon;
  color: string;
  /** ID do agente no backend (para verificar acesso via plan_limits) */
  backendId: string;
}

const agents: Agent[] = [
  {
    id: 'clientes',
    name: 'Clientes e Agenda',
    description: 'Cadastre Clientes, Organize Compromissos, Veja Quem Precisa de Atenção e Acompanhe Suas Vendas',
    icon: Users,
    color: 'from-green-500 to-emerald-500',
    backendId: 'clientes'
  },
  {
    id: 'financeiro',
    name: 'Financeiro',
    description: 'Controle Seu Dinheiro, Cobranças, Notas Fiscais, Boleto Mensal do MEI e Limite de Faturamento — Tudo num Lugar Só',
    icon: DollarSign,
    color: 'from-emerald-500 to-teal-500',
    backendId: 'contabilidade'
  },
  {
    id: 'assistente',
    name: 'Assistente Pessoal',
    description: 'Seu Ajudante de IA — Resumo do Dia, Alertas, Sugestões e Automações Inteligentes',
    icon: Bot,
    color: 'from-blue-500 to-indigo-500',
    backendId: 'assistente'
  }
];

export default function Agents() {
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const { isAgentAvailable, isFree, loading } = usePlanLimits();

  const handleAgentClick = (agent: Agent) => {
    if (isAgentAvailable(agent.backendId)) {
      navigate(`/agents/${agent.id}`);
    } else {
      navigate('/pricing');
    }
  };

  // Conta quantos agentes estão disponíveis
  const availableCount = agents.filter(a => isAgentAvailable(a.backendId)).length;

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white' : 'bg-gradient-to-br from-slate-50 via-white to-slate-100 text-slate-900'}`}>
      {/* Header */}
      <div className={`border-b backdrop-blur-sm ${isDark ? 'border-slate-700/50 bg-slate-900/50' : 'border-slate-200 bg-white/80'}`}>
        <div className="max-w-6xl mx-auto px-6 py-4">
          <button
            onClick={() => navigate('/dashboard')}
            className={`flex items-center gap-2 transition mb-4 ${isDark ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-900'}`}
          >
            <ArrowLeft className="w-5 h-5" />
            Voltar
          </button>
          <h1 className="text-3xl font-bold">Seus Agentes</h1>
          <p className={`mt-2 text-base ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            {loading ? 'Carregando...' : `${availableCount} de ${agents.length} agentes disponíveis no seu plano`}
          </p>
        </div>
      </div>

      {/* Agents Grid */}
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => {
            const Icon = agent.icon;
            const hasAccess = isAgentAvailable(agent.backendId);
            
            return (
              <div
                key={agent.id}
                onClick={() => handleAgentClick(agent)}
                className={`relative p-6 rounded-2xl border transition cursor-pointer group ${
                  hasAccess 
                    ? isDark ? 'bg-slate-800/50 border-slate-700/50 hover:border-slate-600' : 'bg-white border-slate-200 hover:border-slate-300 shadow-sm hover:shadow-md'
                    : isDark ? 'bg-slate-800/30 border-slate-700/30' : 'bg-slate-50 border-slate-200/50'
                }`}
              >
                {/* Lock overlay for non-accessible */}
                {!hasAccess && (
                  <div className={`absolute inset-0 rounded-2xl flex items-center justify-center z-10 ${isDark ? 'bg-slate-900/60' : 'bg-white/60 backdrop-blur-[2px]'}`}>
                    <div className="text-center">
                      <Lock className={`w-8 h-8 mx-auto mb-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                      <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Fazer Upgrade</span>
                    </div>
                  </div>
                )}

                <div className="flex items-start justify-between mb-4">
                  <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${agent.color} flex items-center justify-center ${!hasAccess ? 'opacity-50' : ''}`}>
                    <Icon className="w-7 h-7 text-white" />
                  </div>
                  {hasAccess && (
                    <span className="flex items-center gap-1.5 text-xs">
                      <span className={`w-2 h-2 rounded-full animate-pulse ${isDark ? 'bg-green-400' : 'bg-green-500'}`} />
                      <span className={isDark ? 'text-green-400' : 'text-green-600'}>Online</span>
                    </span>
                  )}
                </div>
                
                <h3 className={`text-xl font-semibold mb-2 transition ${hasAccess ? isDark ? 'text-white group-hover:text-green-400' : 'text-slate-900 group-hover:text-green-600' : isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  {agent.name}
                </h3>
                <p className={`text-base leading-relaxed ${hasAccess ? isDark ? 'text-slate-400' : 'text-slate-600' : isDark ? 'text-slate-600' : 'text-slate-400'}`}>
                  {agent.description}
                </p>

                {hasAccess && (
                  <button className="mt-4 w-full py-3 px-4 rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white text-base font-medium transition shadow-lg shadow-green-500/20">
                    Conversar
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* Upgrade Banner for Free users */}
        {isFree && !loading && (
          <div className={`mt-8 p-6 rounded-2xl bg-gradient-to-r border ${isDark ? 'from-green-900/30 to-emerald-900/30 border-green-700/30' : 'from-green-50 to-emerald-50 border-green-200'}`}>
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <div className="flex-1">
                <h3 className={`font-semibold text-lg ${isDark ? 'text-white' : 'text-slate-900'}`}>Desbloqueie Mais Agentes</h3>
                <p className={`text-base ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  A partir de R$ 39,90/mês, acesse até 3 agentes com o plano Essencial
                </p>
              </div>
              <button
                onClick={() => navigate('/pricing')}
                className="px-6 py-3 rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white font-medium transition"
              >
                Ver Planos
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
