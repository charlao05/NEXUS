/**
 * PlanSwitcher — Componente de troca de plano no header
 * 
 * Para admins: dropdown que permite trocar de plano instantaneamente (para testes)
 * Para users normais: mostra plano atual + botão de upgrade se não é enterprise
 */
import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { apiUrl } from '../config/api'

interface PlanInfo {
  displayName: string
  color: string
  gradient: string
  icon: string
}

const PLAN_MAP: Record<string, PlanInfo> = {
  free:          { displayName: 'Gratuito',      color: 'text-slate-400',  gradient: 'from-slate-500 to-slate-600',     icon: '🆓' },
  essencial:     { displayName: 'Essencial',     color: 'text-blue-400',   gradient: 'from-blue-500 to-cyan-500',       icon: '⚡' },
  profissional:  { displayName: 'Profissional',  color: 'text-green-400',  gradient: 'from-green-500 to-emerald-500',   icon: '⭐' },
  completo:      { displayName: 'Completo',      color: 'text-purple-400', gradient: 'from-purple-500 to-indigo-500',   icon: '👑' },
  // backward compat aliases
  pro:           { displayName: 'Essencial',     color: 'text-blue-400',   gradient: 'from-blue-500 to-cyan-500',       icon: '⚡' },
  enterprise:    { displayName: 'Completo',      color: 'text-purple-400', gradient: 'from-purple-500 to-indigo-500',   icon: '👑' },
}

// Chaves exibidas no dropdown (sem aliases)
const DISPLAY_PLANS = ['free', 'essencial', 'profissional', 'completo']

interface PlanSwitcherProps {
  currentPlan: string
  isAdmin: boolean
  token: string | null
  isDark: boolean
  onPlanChanged: (plan: string, newToken?: string) => void
}

export default function PlanSwitcher({ currentPlan, isAdmin, token, isDark, onPlanChanged }: PlanSwitcherProps) {
  const [open, setOpen] = useState(false)
  const [switching, setSwitching] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const planInfo = PLAN_MAP[currentPlan] || PLAN_MAP.free

  // Fechar dropdown ao clicar fora
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const [error, setError] = useState<string | null>(null)

  const handleSwitchPlan = async (plan: string) => {
    if (plan === currentPlan) { setOpen(false); return }
    setError(null)

    if (isAdmin) {
      // Admin: troca instantaneamente via API
      setSwitching(true)
      try {
        const resp = await axios.post(apiUrl('/api/auth/admin/switch-plan'), { plan }, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: 8000, // 8s — evita travar se backend não responder
        })
        if (resp.data.access_token) {
          localStorage.setItem('access_token', resp.data.access_token)
          localStorage.setItem('user_plan', plan)
        }
        onPlanChanged(plan, resp.data.access_token)
      } catch (err: unknown) {
        const msg = axios.isAxiosError(err)
          ? err.code === 'ECONNABORTED'
            ? 'Timeout — backend pode estar offline'
            : err.response?.data?.detail || `Erro ${err.response?.status || 'de rede'}`
          : 'Erro inesperado'
        setError(msg)
        console.error('Erro ao trocar plano:', err)
      } finally {
        setSwitching(false)
      }
    } else {
      // User normal: redireciona para pricing/checkout
      setOpen(false)
      navigate('/pricing')
    }
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Botão principal — mostra o plano atual */}
      <button
        onClick={() => { setOpen(!open); setError(null) }}
        className={`
          flex items-center gap-2 px-3 py-1.5 rounded-full
          bg-gradient-to-r ${planInfo.gradient}
          text-white text-sm font-medium
          hover:opacity-90 transition-all duration-200
          ${open ? 'ring-2 ring-white/30' : ''}
        `}
        title={isAdmin ? 'Trocar plano (admin)' : 'Ver Planos'}
      >
        <span className="text-xs">{planInfo.icon}</span>
        <span>{planInfo.displayName}</span>
        <svg className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div className={`
          absolute right-0 mt-2 w-64 rounded-xl shadow-xl border z-50
          ${isDark 
            ? 'bg-slate-800 border-slate-700 shadow-black/40' 
            : 'bg-white border-slate-200 shadow-slate-200/50'}
        `}>
          {/* Header */}
          <div className={`px-4 py-3 border-b ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
            <p className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {isAdmin ? '🔧 Admin — Trocar plano para teste' : 'Seu plano atual'}
            </p>
          </div>

          {/* Plan options */}
          <div className="py-1">
            {DISPLAY_PLANS.map((planKey) => {
              const info = PLAN_MAP[planKey]
              const isActive = planKey === currentPlan || (planKey === 'essencial' && currentPlan === 'pro') || (planKey === 'completo' && currentPlan === 'enterprise')
              return (
                <button
                  key={planKey}
                  onClick={() => handleSwitchPlan(planKey)}
                  disabled={switching}
                  className={`
                    w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors
                    ${isActive 
                      ? isDark ? 'bg-slate-700/50' : 'bg-slate-50' 
                      : isDark ? 'hover:bg-slate-700/30' : 'hover:bg-slate-50'}
                    ${switching ? 'opacity-50 cursor-wait' : ''}
                  `}
                >
                  <span className="text-base">{info.icon}</span>
                  <div className="flex-1">
                    <p className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      {info.displayName}
                    </p>
                    <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                      {planKey === 'free' && '10 msg/dia • 1 agente'}
                      {planKey === 'essencial' && 'R$ 39,90/mês • 3 agentes'}
                      {planKey === 'profissional' && 'R$ 69,90/mês • Todos agentes'}
                      {planKey === 'completo' && 'R$ 99,90/mês • Ilimitado'}
                    </p>
                  </div>
                  {isActive && (
                    <span className={`text-xs px-2 py-0.5 rounded-full ${isDark ? 'bg-green-900/50 text-green-400' : 'bg-green-100 text-green-700'}`}>
                      Atual
                    </span>
                  )}
                  {!isActive && !isAdmin && (
                    <span className={`text-xs ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                      Upgrade →
                    </span>
                  )}
                  {!isActive && isAdmin && (
                    <span className={`text-xs ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>
                      Testar
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Footer */}
          {error && (
            <div className={`px-4 py-2 border-t ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
              <p className="text-xs text-red-400">⚠️ {error}</p>
              <button onClick={() => setError(null)} className="text-xs text-slate-400 hover:text-slate-300 mt-1 underline">
                Fechar
              </button>
            </div>
          )}
          {!isAdmin && currentPlan !== 'completo' && currentPlan !== 'enterprise' && (
            <div className={`px-4 py-3 border-t ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
              <button
                onClick={() => { setOpen(false); navigate('/pricing') }}
                className="w-full py-2 rounded-lg bg-gradient-to-r from-green-500 to-emerald-500 text-white text-sm font-medium hover:opacity-90 transition"
              >
                Ver todos os planos
              </button>
            </div>
          )}

          {isAdmin && (
            <div className={`px-4 py-2 border-t ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
              <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                ⚠️ Troca imediata para testes. O token é atualizado automaticamente.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
