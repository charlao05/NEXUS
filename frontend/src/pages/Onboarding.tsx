import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'
import { apiUrl } from '../config/api'

export default function Onboarding() {
  const { token } = useAuth()
  const [currentStep, setCurrentStep] = useState(0)
  const [businessName, setBusinessName] = useState('')
  const [businessType, setBusinessType] = useState('')
  const [goals, setGoals] = useState<string[]>([])
  
  const BUSINESS_TYPES = [
    { id: 'servicos', label: 'Prestação de Serviços', icon: '🔧' },
    { id: 'comercio', label: 'Comércio', icon: '🛒' },
    { id: 'saude', label: 'Saúde e Bem-estar', icon: '💆' },
    { id: 'alimentacao', label: 'Alimentação', icon: '🍽️' },
    { id: 'educacao', label: 'Educação', icon: '📚' },
    { id: 'tecnologia', label: 'Tecnologia', icon: '💻' },
    { id: 'outro', label: 'Outro', icon: '📋' },
  ]

  const GOALS = [
    { id: 'clientes', label: 'Gerenciar Clientes', icon: '👥' },
    { id: 'agenda', label: 'Controlar Agendamentos', icon: '📅' },
    { id: 'financeiro', label: 'Contabilidade MEI Completa', icon: '📊' },
    { id: 'nf', label: 'Emitir Notas Fiscais', icon: '📄' },
    { id: 'cobranca', label: 'Automatizar Cobranças', icon: '💳' },
    { id: 'automacao', label: 'Automação Web', icon: '🤖' },
  ]

  const toggleGoal = (id: string) => {
    setGoals(prev => prev.includes(id) ? prev.filter(g => g !== id) : [...prev, id])
  }

  const handleComplete = async () => {
    try {
      // Salvar preferências (o backend pode armazenar isso futuramente)
      localStorage.setItem('onboarding_completed', 'true')
      localStorage.setItem('business_name', businessName)
      localStorage.setItem('business_type', businessType)
      localStorage.setItem('user_goals', JSON.stringify(goals))

      // Registrar atividade
      if (token) {
        await axios.post(apiUrl('/api/chat/save'), {
          agent_id: 'system',
          role: 'assistant',
          content: `Onboarding completo: ${businessName} (${businessType}). Objetivos: ${goals.join(', ')}`,
        }, { headers: { Authorization: `Bearer ${token}` } }).catch((err) => console.warn('Falha ao salvar onboarding:', err?.message))
      }

            window.location.href = '/dashboard'
    } catch {
            window.location.href = '/dashboard'
    }
  }

  const steps = [
    // Step 0: Boas-vindas
    <div key="welcome" className="text-center space-y-6">
      <div className="text-6xl mb-2">🚀</div>
      <h2 className="text-3xl font-bold text-white">Bem-vindo ao NEXUS!</h2>
      <p className="text-slate-400 text-lg max-w-md mx-auto">
        Seu assistente de IA para MEI e pequenos negócios. Vamos configurar tudo em menos de 1 minuto.
      </p>
      <button
        onClick={() => setCurrentStep(1)}
        className="px-8 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl font-semibold hover:from-green-400 hover:to-emerald-400 transition-all shadow-lg shadow-green-500/25"
      >
        Começar →
      </button>
    </div>,

    // Step 1: Nome do negócio
    <div key="business" className="space-y-6">
      <div className="text-center">
        <div className="text-4xl mb-2">🏪</div>
        <h2 className="text-2xl font-bold text-white">Qual o nome do seu negócio?</h2>
        <p className="text-slate-400 mt-1">Isso personaliza sua experiência</p>
      </div>
      <input
        type="text"
        value={businessName}
        onChange={e => setBusinessName(e.target.value)}
        placeholder="Ex: Studio Maria, Oficina do João..."
        className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500"
        autoFocus
      />
      <div className="flex justify-between">
        <button
          onClick={() => setCurrentStep(0)}
          className="px-6 py-2 text-slate-400 hover:text-white transition-colors"
        >
          ← Voltar
        </button>
        <button
          onClick={() => setCurrentStep(2)}
          disabled={!businessName.trim()}
          className="px-8 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl font-semibold hover:from-green-400 hover:to-emerald-400 transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-green-500/25"
        >
          Continuar →
        </button>
      </div>
    </div>,

    // Step 2: Tipo de negócio
    <div key="type" className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white">Qual o tipo do seu negócio?</h2>
        <p className="text-slate-400 mt-1">Selecionamos os agentes ideais para você</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {BUSINESS_TYPES.map(t => (
          <button
            key={t.id}
            onClick={() => setBusinessType(t.id)}
            className={`p-4 rounded-xl border transition-all text-left ${
              businessType === t.id
                ? 'border-green-500 bg-green-500/10 shadow-lg shadow-green-500/10'
                : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
            }`}
          >
            <span className="text-2xl">{t.icon}</span>
            <p className={`mt-1 font-medium ${businessType === t.id ? 'text-green-400' : 'text-slate-300'}`}>
              {t.label}
            </p>
          </button>
        ))}
      </div>
      <div className="flex justify-between">
        <button onClick={() => setCurrentStep(1)} className="px-6 py-2 text-slate-400 hover:text-white transition-colors">
          ← Voltar
        </button>
        <button
          onClick={() => setCurrentStep(3)}
          disabled={!businessType}
          className="px-8 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl font-semibold hover:from-green-400 hover:to-emerald-400 transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-green-500/25"
        >
          Continuar →
        </button>
      </div>
    </div>,

    // Step 3: Objetivos
    <div key="goals" className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white">O que você precisa resolver?</h2>
        <p className="text-slate-400 mt-1">Selecione tudo que se aplica</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {GOALS.map(g => (
          <button
            key={g.id}
            onClick={() => toggleGoal(g.id)}
            className={`p-4 rounded-xl border transition-all text-left ${
              goals.includes(g.id)
                ? 'border-green-500 bg-green-500/10 shadow-lg shadow-green-500/10'
                : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
            }`}
          >
            <span className="text-2xl">{g.icon}</span>
            <p className={`mt-1 font-medium ${goals.includes(g.id) ? 'text-green-400' : 'text-slate-300'}`}>
              {g.label}
            </p>
          </button>
        ))}
      </div>
      <div className="flex justify-between">
        <button onClick={() => setCurrentStep(2)} className="px-6 py-2 text-slate-400 hover:text-white transition-colors">
          ← Voltar
        </button>
        <button
          onClick={handleComplete}
          disabled={goals.length === 0}
          className="px-8 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl font-semibold hover:from-green-400 hover:to-emerald-400 transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-green-500/25"
        >
          Concluir ✓
        </button>
      </div>
    </div>,
  ]

      return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Progress bar */}
        <div className="flex gap-2 mb-8">
          {[0, 1, 2, 3].map(i => (
            <div
              key={i}
              className={`h-1.5 flex-1 rounded-full transition-all duration-300 ${
                i <= currentStep ? 'bg-green-500' : 'bg-slate-700'
              }`}
            />
          ))}
        </div>

        {/* Step content */}
        <div className="bg-slate-800/60 backdrop-blur-xl border border-slate-700/50 rounded-2xl p-8 shadow-2xl">
          {steps[currentStep]}
        </div>

        {/* Skip button */}
        {currentStep > 0 && (
          <div className="text-center mt-4">
            <button
              onClick={() => {
                localStorage.setItem('onboarding_completed', 'true')
                              window.location.href = '/dashboard'
              }}
              className="text-sm text-slate-500 hover:text-slate-400 transition-colors"
            >
              Pular e Ir Direto ao Dashboard
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
