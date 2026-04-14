import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useNotifications } from '../hooks/useNotifications'
import { useTheme } from '../contexts/ThemeContext'
import NotificationBell from '../components/NotificationBell'
import PlanSwitcher from '../components/PlanSwitcher'
import axios from 'axios'
import { apiUrl } from '../config/api'

const PLAN_DETAILS: Record<string, { displayName: string; color: string; gradient: string }> = {
  free: { displayName: 'Gratuito', color: 'text-slate-400', gradient: 'from-slate-500 to-slate-600' },
  essencial: { displayName: 'Essencial', color: 'text-blue-400', gradient: 'from-blue-500 to-cyan-500' },
  profissional: { displayName: 'Profissional', color: 'text-green-400', gradient: 'from-green-500 to-emerald-500' },
  completo: { displayName: 'Completo', color: 'text-purple-400', gradient: 'from-purple-500 to-indigo-500' },
  // backward compat aliases
  pro: { displayName: 'Essencial', color: 'text-blue-400', gradient: 'from-blue-500 to-cyan-500' },
  enterprise: { displayName: 'Completo', color: 'text-purple-400', gradient: 'from-purple-500 to-indigo-500' }
};

interface CRMDashboard {
  clients: {
    total: number;
    inactive: number;
    segments: Record<string, number>;
    need_followup: number;
    avg_purchase_score: number;
    avg_churn_risk: number;
  };
  revenue: {
    total: number;
    avg_ticket: number;
  };
  appointments_today: number;
  pipeline: {
    pipeline: Record<string, { count: number; value: number; weighted_value: number }>;
    total_value: number;
    weighted_forecast: number;
    won_count: number;
    won_value: number;
    lost_count: number;
    win_rate: number;
  };
}

interface AnalyticsData {
  overview: {
    total_clients: number;
    active_clients: number;
    month_revenue: number;
    month_expenses: number;
    month_profit: number;
    pipeline_value: number;
    pipeline_count: number;
    appointments_today: number;
  };
  mei: {
    year_revenue: number;
    limit: number;
    percent_used: number;
    remaining: number;
  };
  activity_timeline: Array<{
    action: string;
    agent_id: string | null;
    details: string;
    created_at: string;
  }>;
  chat_usage: Record<string, number>;
  revenue_chart: Array<{ date: string; value: number }>;
  clients_chart: Array<{ week: string; count: number }>;
}

/** Capitaliza cada palavra do nome (ex: "charles silva" → "Charles Silva") */
const toTitleCase = (name: string): string =>
  name.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ')

function Dashboard() {
  const { logout, token, userRole: authRole } = useAuth()
  const navigate = useNavigate()
  const { isDark, toggleTheme } = useTheme()
  const { notifications, unreadCount, markRead, clearAll } = useNotifications(token)
  const [userPlan, setUserPlan] = useState<string>('free')
  const [planReady, setPlanReady] = useState(false)
  const [userRole, setUserRole] = useState<string>(() => authRole || localStorage.getItem('user_role') || 'user')
  const [userName, setUserName] = useState<string>('')
  const [userEmail, setUserEmail] = useState<string>('')
  const [requestsUsed, setRequestsUsed] = useState(0)
  const [requestsLimit, setRequestsLimit] = useState(100)
  const [crmData, setCrmData] = useState<CRMDashboard | null>(null)
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)

  useEffect(() => {
    const savedName = localStorage.getItem('user_name')
    const savedEmail = localStorage.getItem('user_email')
    const savedPlan = localStorage.getItem('user_plan')
    const savedRole = localStorage.getItem('user_role')
    if (savedName) setUserName(toTitleCase(savedName))
    if (savedEmail) setUserEmail(savedEmail)
    if (savedPlan) setUserPlan(savedPlan)
    if (savedRole) setUserRole(savedRole)

    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        setUserPlan(payload.plan || savedPlan || 'free')
        if (payload.role) setUserRole(payload.role)
        const emailFromToken = payload.email || ''
        setUserEmail(emailFromToken)
        if (!savedName && emailFromToken) {
          const nameFromEmail = emailFromToken.split('@')[0].replace(/[._]/g, ' ')
          const formattedName = nameFromEmail.split(' ').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
          setUserName(formattedName)
          localStorage.setItem('user_name', formattedName)
        }
      } catch (e) {
        console.error('Erro ao decodificar token:', e)
      }
    }
    // Plano já conhecido via localStorage/token — pode renderizar agentes
    setPlanReady(true)

    // Buscar perfil (requests usage) + CRM + Analytics em paralelo
    const fetchProfile = async () => {
      try {
        const response = await axios.get(apiUrl('/api/auth/me'), {
          headers: { Authorization: `Bearer ${token}` }
        })
        if (response.data) {
          if (response.data.plan) {
            setUserPlan(response.data.plan)
            localStorage.setItem('user_plan', response.data.plan)
          }
          if (response.data.full_name && response.data.full_name !== 'Usuário') {
            const titleCased = toTitleCase(response.data.full_name)
            setUserName(titleCased)
            localStorage.setItem('user_name', titleCased)
          }
          if (response.data.email) {
            setUserEmail(response.data.email)
          }
          setRequestsUsed(response.data.requests_used || 0)
          setRequestsLimit(response.data.requests_limit || 100)
          if (response.data.role) {
            setUserRole(response.data.role)
            localStorage.setItem('user_role', response.data.role)
          }
        }
      } catch {
        // Dados do token/localStorage já estão setados acima
      }
    }

    // Buscar dados reais do CRM
    const fetchCRM = async () => {
      try {
        const response = await axios.get(apiUrl('/api/crm/dashboard'), {
          headers: { Authorization: `Bearer ${token}` }
        })
        if (response.data) {
          setCrmData(response.data)
        }
      } catch {
        // CRM dashboard indisponível
      }
    }

    // Buscar analytics avançado
    const fetchAnalytics = async () => {
      try {
        const response = await axios.get(apiUrl('/api/analytics/dashboard'), {
          headers: { Authorization: `Bearer ${token}` }
        })
        if (response.data) {
          setAnalytics(response.data)
        }
      } catch {
        // Analytics indisponível
      }
    }

    if (token) {
      // Todas as chamadas em paralelo — UI renderiza instantaneamente com dados do localStorage
      fetchProfile()
      fetchCRM()
      fetchAnalytics()
    }
  }, [token])

  const planInfo = PLAN_DETAILS[userPlan] || PLAN_DETAILS.free
  const usagePercent = Math.min((requestsUsed / requestsLimit) * 100, 100)

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
  }

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-slate-100' : 'bg-gradient-to-br from-slate-50 via-white to-slate-100 text-slate-900'}`}>
      {/* Top Navigation */}
      <nav className={`border-b sticky top-0 z-50 backdrop-blur-sm ${isDark ? 'border-slate-700/50 bg-slate-900/50' : 'border-slate-200 bg-white/80'}`}>
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center">
              <span className="text-white font-bold text-lg">N</span>
            </div>
            <span className={`text-xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>NEXUS</span>
          </div>

          <div className="flex items-center gap-4">
            {/* Plan Switcher */}
            <PlanSwitcher
              currentPlan={userPlan}
              isAdmin={userRole === 'admin' || userRole === 'superadmin'}
              token={token}
              isDark={isDark}
              onPlanChanged={(plan, newToken) => {
                setUserPlan(plan)
                localStorage.setItem('user_plan', plan)
                if (newToken) {
                  localStorage.setItem('access_token', newToken)
                  window.location.reload()
                }
              }}
            />
            
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className={`p-2 rounded-lg transition ${isDark ? 'bg-slate-700/50 text-yellow-400 hover:bg-slate-600' : 'bg-slate-200 text-slate-600 hover:bg-slate-300'}`}
              title={isDark ? 'Modo claro' : 'Modo escuro'}
            >
              {isDark ? (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              )}
            </button>

            {/* Notifications + User Menu */}
            <div className="flex items-center gap-3">
              <NotificationBell
                notifications={notifications}
                unreadCount={unreadCount}
                onMarkRead={markRead}
                onClearAll={clearAll}
              />
              <button
                onClick={() => navigate('/profile')}
                className={`w-9 h-9 rounded-full flex items-center justify-center transition hover:ring-2 hover:ring-green-500/50 ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}
                title="Meu Perfil"
              >
                <span className={`text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                  {(userName || userEmail || 'U').charAt(0).toUpperCase()}
                </span>
              </button>
              <button
                onClick={logout}
                className={`px-4 py-2 rounded-lg transition text-sm ${isDark ? 'bg-slate-700/50 text-slate-300 hover:bg-slate-600 hover:text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900'}`}
              >
                Sair
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className={`text-3xl font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
            Olá{userName ? `, ${userName.split(' ')[0]}` : ''}! 👋
          </h1>
          <p className={isDark ? 'text-slate-400' : 'text-slate-500'}>
            Bem-vindo ao seu painel de controle NEXUS
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          {/* Usage Card */}
          <div className={`p-6 rounded-2xl border ${isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-sm'}`}>
            <div className="flex items-center justify-between mb-4">
              <h3 className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Uso Hoje</h3>
              <svg className={`w-5 h-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="mb-3">
              <span className={`text-3xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>{requestsUsed}</span>
              <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}> / {requestsLimit === Infinity ? '∞' : requestsLimit}</span>
            </div>
            <div className={`w-full h-2 rounded-full overflow-hidden ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
              <div 
                className={`h-full transition-all duration-500 ${usagePercent > 80 ? 'bg-red-500' : 'bg-green-500'}`}
                style={{ width: `${usagePercent}%` }}
              />
            </div>
          </div>

          {/* Plan Card */}
          <div className={`p-6 rounded-2xl border ${isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-sm'}`}>
            <div className="flex items-center justify-between mb-4">
              <h3 className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Seu Plano</h3>
              <svg className={`w-5 h-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
              </svg>
            </div>
            <div className={`text-3xl font-bold ${planInfo.color} mb-2`}>
              {planInfo.displayName}
            </div>
            {userPlan === 'free' && (
              <button
                onClick={() => navigate('/pricing')}
                className="text-sm text-green-400 hover:text-green-300 transition"
              >
                Fazer Upgrade →
              </button>
            )}
          </div>

          {/* Quick Access Card */}
          <div className={`p-6 rounded-2xl border ${isDark ? 'bg-gradient-to-br from-green-900/30 to-emerald-900/30 border-green-700/30' : 'bg-gradient-to-br from-green-50 to-emerald-50 border-green-200'}`}>
            <div className="flex items-center justify-between mb-4">
              <h3 className={`text-sm font-medium ${isDark ? 'text-green-400' : 'text-green-700'}`}>Acesso Rápido</h3>
              <svg className={`w-5 h-5 ${isDark ? 'text-green-500' : 'text-green-600'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <p className={`text-sm mb-3 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
              Fale com seu agente de clientes agora
            </p>
            <button
              onClick={() => navigate('/agents/clientes')}
              className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg text-sm font-medium transition"
            >
              Abrir Agente →
            </button>
          </div>
        </div>

        {/* CRM Real Stats */}
        {crmData && (
          <div className="grid md:grid-cols-4 gap-4 mb-8">
            <div className={`p-4 rounded-xl border ${isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-sm'}`}>
              <p className={`text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Clientes</p>
              <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>{crmData.clients.total - crmData.clients.inactive}</p>
              <p className={`text-xs mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{crmData.clients.total} Total</p>
            </div>
            <div className={`p-4 rounded-xl border ${isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-sm'}`}>
              <p className={`text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Vendas em Andamento</p>
              <p className={`text-2xl font-bold ${isDark ? 'text-green-400' : 'text-green-600'}`}>{formatCurrency(crmData.pipeline.total_value)}</p>
              <p className={`text-xs mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Taxa de Sucesso: {(crmData.pipeline.win_rate * 100).toFixed(0)}%</p>
            </div>
            <div className={`p-4 rounded-xl border ${isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-sm'}`}>
              <p className={`text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Receita Total</p>
              <p className={`text-2xl font-bold ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>{formatCurrency(crmData.revenue.total)}</p>
              <p className={`text-xs mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Valor Médio por Venda: {formatCurrency(crmData.revenue.avg_ticket)}</p>
            </div>
            <div className={`p-4 rounded-xl border ${isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-sm'}`}>
              <p className={`text-xs font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Agendamentos Hoje</p>
              <p className={`text-2xl font-bold ${isDark ? 'text-cyan-400' : 'text-cyan-600'}`}>{crmData.appointments_today}</p>
              <p className={`text-xs mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{crmData.clients.need_followup} Precisam de Contato</p>
            </div>
          </div>
        )}

        {/* Analytics Avançado */}
        {analytics && (
          <div className="grid md:grid-cols-2 gap-6 mb-8">
            {/* MEI Limit Tracker */}
            <div className={`p-5 rounded-2xl border ${isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-sm'}`}>
              <div className="flex items-center justify-between mb-3">
                <h3 className={`font-semibold flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  <span className="text-lg">📊</span> Limite MEI 2026
                </h3>
                <span className={`text-sm font-bold ${analytics.mei.percent_used > 80 ? 'text-red-400' : analytics.mei.percent_used > 60 ? 'text-amber-400' : 'text-green-400'}`}>
                  {analytics.mei.percent_used}%
                </span>
              </div>
              <div className={`w-full h-3 rounded-full overflow-hidden mb-2 ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    analytics.mei.percent_used > 80 ? 'bg-red-500' : analytics.mei.percent_used > 60 ? 'bg-amber-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min(analytics.mei.percent_used, 100)}%` }}
                />
              </div>
              <div className="flex justify-between text-sm">
                <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>
                  {formatCurrency(analytics.mei.year_revenue)} faturado
                </span>
                <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>
                  {formatCurrency(analytics.mei.remaining)} restante
                </span>
              </div>
              <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                Limite anual: {formatCurrency(analytics.mei.limit)}
              </p>
            </div>

            {/* Lucro do Mês */}
            <div className={`p-5 rounded-2xl border ${isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-sm'}`}>
              <h3 className={`font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                <span className="text-lg">💰</span> Resultado do Mês
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Receitas</span>
                  <span className={`font-bold ${isDark ? 'text-green-400' : 'text-green-600'}`}>{formatCurrency(analytics.overview.month_revenue)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Despesas</span>
                  <span className={`font-bold ${isDark ? 'text-red-400' : 'text-red-600'}`}>- {formatCurrency(analytics.overview.month_expenses)}</span>
                </div>
                <div className={`border-t pt-2 flex justify-between items-center ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>Lucro</span>
                  <span className={`text-lg font-bold ${analytics.overview.month_profit >= 0 ? (isDark ? 'text-green-400' : 'text-green-600') : (isDark ? 'text-red-400' : 'text-red-600')}`}>
                    {formatCurrency(analytics.overview.month_profit)}
                  </span>
                </div>
              </div>
              {analytics.revenue_chart.length > 0 && (
                <div className="mt-4">
                  <p className={`text-xs mb-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Receita Últimos 30 Dias</p>
                  <div className="flex items-end gap-px h-12">
                    {analytics.revenue_chart.slice(-30).map((d, i) => {
                      const maxVal = Math.max(...analytics.revenue_chart.map(r => r.value), 1)
                      const height = Math.max((d.value / maxVal) * 100, 4)
                      return (
                        <div
                          key={i}
                          className="flex-1 bg-green-500/60 hover:bg-green-400 rounded-t transition-colors"
                          style={{ height: `${height}%` }}
                          title={`${d.date}: ${formatCurrency(d.value)}`}
                        />
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Activity Timeline + Chat Usage */}
        {analytics && (analytics.activity_timeline.length > 0 || Object.keys(analytics.chat_usage).length > 0) && (
          <div className="grid md:grid-cols-2 gap-6 mb-8">
            {/* Timeline */}
            {analytics.activity_timeline.length > 0 && (() => {
              const actionLabels: Record<string, string> = {
                daily_cashflow: 'Resumo do dia',
                weekly_cashflow: 'Resumo da semana',
                range_cashflow: 'Resumo por período',
                payment_breakdown: 'Vendas por pagamento',
                create_client: 'Novo cliente',
                update_client: 'Cliente atualizado',
                delete_client: 'Cliente removido',
                create_appointment: 'Novo compromisso',
                record_transaction: 'Transação registrada',
                create_invoice: 'Nova fatura',
                stock_entry: 'Entrada de estoque',
                stock_exit: 'Saída de estoque',
                create_supplier: 'Novo fornecedor',
                login: 'Login',
                signup: 'Cadastro',
                chat: 'Conversa',
              }
              return (
              <div className={`p-5 rounded-2xl border ${isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-sm'}`}>
                <h3 className={`font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  <span className="text-lg">🕐</span> Atividades Recentes
                </h3>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {analytics.activity_timeline.slice(0, 10).map((a, i) => (
                    <div key={i} className="flex items-start gap-3 text-sm">
                      <span className={`text-xs whitespace-nowrap mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                        {new Date(a.created_at).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                      </span>
                      <div>
                        <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>{actionLabels[a.action] || a.action.replace(/_/g, ' ')}</span>
                        {a.details && <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{a.details}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              )
            })()}

            {/* Chat Usage por Agente */}
            {Object.keys(analytics.chat_usage).length > 0 && (
              <div className={`p-5 rounded-2xl border ${isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-sm'}`}>
                <h3 className={`font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  <span className="text-lg">💬</span> Uso de Chat (7 Dias)
                </h3>
                <div className="space-y-3">
                  {Object.entries(analytics.chat_usage)
                    .sort(([,a], [,b]) => b - a)
                    .map(([agent, count]) => {
                      const maxCount = Math.max(...Object.values(analytics.chat_usage))
                      const pct = Math.round((count / maxCount) * 100)
                      const colors: Record<string, string> = {
                        agenda: 'bg-blue-500', clientes: 'bg-green-500',
                        financeiro: 'bg-emerald-500', contabilidade: 'bg-emerald-500',
                        cobranca: 'bg-red-500', assistente: 'bg-cyan-500',
                      }
                      return (
                        <div key={agent}>
                          <div className="flex justify-between items-center text-sm mb-1">
                            <span className={`capitalize ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{agent}</span>
                            <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>{count} msgs</span>
                          </div>
                          <div className={`w-full h-2 rounded-full overflow-hidden ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
                            <div
                              className={`h-full rounded-full ${colors[agent] || 'bg-slate-500'}`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      )
                    })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Seus Agentes — dinâmico por plano */}
        {(() => {
          const _plan = userPlan?.toLowerCase() || 'free';
          const _paid = ['essencial', 'profissional', 'completo', 'pro', 'enterprise'].includes(_plan);
          const _pro  = ['profissional', 'completo', 'enterprise'].includes(_plan);
          const _isAdmin = userRole === 'admin' || userRole === 'superadmin';

          type AgentCard = { id: string; label: string; desc: string; gradient: string; icon: React.ReactNode; locked?: boolean };
          const allAgents: AgentCard[] = [
            {
              id: 'clientes', label: 'Clientes e Agenda', desc: 'Cadastro, compromissos e acompanhamento',
              gradient: 'from-green-500 to-emerald-500',
              icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />,
            },
            {
              id: 'financeiro', label: 'Financeiro', desc: 'Boleto MEI, limite de faturamento e resumos',
              gradient: 'from-emerald-500 to-teal-500',
              icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />,
            },
            {
              id: 'cobranca', label: 'Cobranças', desc: 'Quem tá devendo, vencimentos e lembretes',
              gradient: 'from-orange-500 to-amber-500',
              icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />,
              locked: !_isAdmin && !_paid,
            },
            {
              id: 'assistente', label: 'Assistente Pessoal', desc: 'Resumo do dia, alertas e automações',
              gradient: 'from-blue-500 to-indigo-500',
              icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />,
              locked: !_isAdmin && !_pro,
            },
          ];

          const upgradeMsg: Record<string, string> = {
            free: 'Desbloqueie Cobranças e o Assistente — a partir de R$ 29,90/mês',
            essencial: 'Desbloqueie o Assistente Pessoal com o plano Profissional (R$ 59,90/mês)',
          };

          return (
            <div className={`p-6 rounded-2xl border ${isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-sm'}`}>
              <h2 className={`text-xl font-semibold mb-4 flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                </svg>
                Seus Agentes
              </h2>
              {!planReady ? (
                <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-3">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className={`h-32 rounded-xl animate-pulse ${isDark ? 'bg-slate-700/40' : 'bg-slate-200/60'}`} />
                  ))}
                </div>
              ) : null}
              <div className={`grid md:grid-cols-2 lg:grid-cols-4 gap-3 ${!planReady ? 'hidden' : ''}`}>
                {allAgents.map(ag => (
                  <button
                    key={ag.id}
                    onClick={() => ag.locked ? navigate('/pricing') : navigate(`/agents/${ag.id}`)}
                    className={`relative flex flex-col gap-3 p-4 rounded-xl border transition text-left group ${
                      ag.locked
                        ? isDark ? 'bg-slate-800/30 border-slate-700/30 opacity-60' : 'bg-slate-50 border-slate-200/50 opacity-60'
                        : isDark ? 'bg-slate-700/30 border-slate-600/30 hover:border-green-500/50' : 'bg-white border-slate-200 hover:border-green-400 hover:shadow-md shadow-sm'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${ag.gradient} flex items-center justify-center`}>
                        <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">{ag.icon}</svg>
                      </div>
                      {ag.locked
                        ? <span className={`text-xs px-2 py-0.5 rounded-full ${isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-100 text-slate-500'}`}>Upgrade</span>
                        : <span className={`flex items-center gap-1 text-xs ${isDark ? 'text-green-400' : 'text-green-600'}`}><span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />Online</span>
                      }
                    </div>
                    <div>
                      <h3 className={`font-semibold text-sm ${isDark ? 'text-white' : 'text-slate-900'}`}>{ag.label}</h3>
                      <p className={`text-xs mt-0.5 leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{ag.desc}</p>
                    </div>
                    {!ag.locked && (
                      <span className={`text-xs font-medium ${isDark ? 'text-green-400 group-hover:text-green-300' : 'text-green-600 group-hover:text-green-700'}`}>
                        Conversar →
                      </span>
                    )}
                  </button>
                ))}
              </div>
              {upgradeMsg[_plan] && !_isAdmin && (
                <div className={`mt-4 flex items-center justify-between p-3 rounded-lg border ${isDark ? 'bg-slate-700/30 border-slate-600/30' : 'bg-slate-50 border-slate-200'}`}>
                  <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {upgradeMsg[_plan]}
                  </p>
                  <button onClick={() => navigate('/pricing')} className="ml-4 text-green-400 hover:text-green-300 text-sm font-medium whitespace-nowrap">
                    Ver Planos →
                  </button>
                </div>
              )}
            </div>
          );
        })()}
      </div>
    </div>
  )
}

export default Dashboard
