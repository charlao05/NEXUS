import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'
import { apiUrl } from '../config/api'

interface AdminOverview {
  users: {
    total: number
    active_24h: number
    active_7d: number
    new_this_month: number
    by_plan: Record<string, number>
  }
  revenue: {
    mrr: number
    active_subscriptions: number
    cancelled_this_month: number
    churn_rate: number
  }
  platform: {
    total_clients: number
    chat_messages_7d: number
    platform_revenue_month: number
  }
}

interface AdminUser {
  id: number
  email: string
  full_name: string
  plan: string
  status: string
  created_at: string
  last_login: string | null
  requests_today: number
}

interface MRRPoint {
  month: string
  label: string
  mrr: number
  new_users: number
}

interface AdminHealthData {
  status: string
  database?: {
    connected: boolean
    size_mb: number
    path: string
  }
  environment: string
  python_version: string
  checked_at?: string
}

export default function AdminDashboard() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [mrrChart, setMrrChart] = useState<MRRPoint[]>([])
  const [totalUsers, setTotalUsers] = useState(0)
  const [page, setPage] = useState(1)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterPlan, setFilterPlan] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'system' | 'feedbacks'>('overview')
  const [feedbacks, setFeedbacks] = useState<Array<{
    id: number; user_id: number; agent_id?: string; rating: number;
    category?: string; message?: string; page?: string; created_at: string;
  }>>([])
  const [feedbacksLoading, setFeedbacksLoading] = useState(false)

  const fetchOverview = useCallback(async () => {
    const headers = { Authorization: `Bearer ${token}` }
    try {
      const [overviewRes, mrrRes] = await Promise.all([
        axios.get(apiUrl('/api/admin/overview'), { headers }),
        axios.get(apiUrl('/api/admin/mrr-chart'), { headers }),
      ])
      setOverview(overviewRes.data)
      setMrrChart(mrrRes.data.chart || [])
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 403) {
        setError('Acesso restrito a administradores')
      } else if (axios.isAxiosError(err) && err.response?.status === 401) {
        setError('Sessão expirada. Faça login novamente.')
      } else {
        setError('Erro ao carregar dados do painel. Verifique sua conexão.')
      }
    }
  }, [token])

  const fetchUsers = useCallback(async () => {
    const headers = { Authorization: `Bearer ${token}` }
    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: '15',
        ...(searchTerm && { search: searchTerm }),
        ...(filterPlan && { plan: filterPlan }),
      })
      const res = await axios.get(apiUrl(`/api/admin/users?${params}`), { headers })
      setUsers(res.data.users || [])
      setTotalUsers(res.data.total || 0)
    } catch {
      setError(prev => prev || 'Erro ao carregar lista de usuários.')
    }
  }, [token, page, searchTerm, filterPlan])

  useEffect(() => {
    setLoading(true)
    Promise.all([fetchOverview(), fetchUsers()]).finally(() => setLoading(false))
  }, [fetchOverview, fetchUsers])

  const fmt = (n: number) =>
    new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(n)

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="text-5xl">🔒</div>
          <h2 className="text-2xl font-bold text-white">{error}</h2>
          <button onClick={() => navigate('/dashboard')} className="px-6 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600">
            Voltar
          </button>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="w-10 h-10 rounded-full border-4 border-slate-700 border-t-purple-400 animate-spin" />
      </div>
    )
  }

  const maxMrr = Math.max(...mrrChart.map(m => m.mrr), 1)

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/dashboard')} className="text-slate-400 hover:text-white text-sm">
              ← Dashboard
            </button>
            <span className="text-slate-600">|</span>
            <h1 className="text-lg font-bold bg-gradient-to-r from-purple-400 to-indigo-400 bg-clip-text text-transparent">
              Admin Panel
            </h1>
          </div>
          <div className="flex items-center gap-4">
            {['overview', 'users', 'feedbacks', 'system'].map(tab => (
              <button
                key={tab}
                onClick={() => {
                  setActiveTab(tab as 'overview' | 'users' | 'system' | 'feedbacks')
                  if (tab === 'feedbacks' && feedbacks.length === 0) {
                    setFeedbacksLoading(true)
                    axios.get(apiUrl('/api/auth/feedbacks'), { headers: { Authorization: `Bearer ${token}` } })
                      .then(res => setFeedbacks(res.data.feedbacks || []))
                      .catch((err) => console.warn('Falha ao carregar feedbacks:', err?.message))
                      .finally(() => setFeedbacksLoading(false))
                  }
                }}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  activeTab === tab ? 'bg-purple-500/20 text-purple-300' : 'text-slate-400 hover:text-white'
                }`}
              >
                {tab === 'overview' ? '📊 Overview' : tab === 'users' ? '👥 Usuários' : tab === 'feedbacks' ? '💬 Feedbacks' : '⚙️ Sistema'}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* TAB: OVERVIEW */}
        {activeTab === 'overview' && overview && (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
                <p className="text-slate-400 text-xs uppercase tracking-wide">Usuários Total</p>
                <p className="text-2xl font-bold text-white mt-1">{overview.users.total}</p>
                <p className="text-green-400 text-xs mt-1">+{overview.users.new_this_month} este mês</p>
              </div>
              <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
                <p className="text-slate-400 text-xs uppercase tracking-wide">Ativos (7d)</p>
                <p className="text-2xl font-bold text-white mt-1">{overview.users.active_7d}</p>
                <p className="text-slate-500 text-xs mt-1">{overview.users.active_24h} nas últimas 24h</p>
              </div>
              <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
                <p className="text-slate-400 text-xs uppercase tracking-wide">Receita Mensal</p>
                <p className="text-2xl font-bold text-green-400 mt-1">{fmt(overview.revenue.mrr)}</p>
                <p className="text-slate-500 text-xs mt-1">{overview.revenue.active_subscriptions} assinaturas</p>
              </div>
              <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
                <p className="text-slate-400 text-xs uppercase tracking-wide">Taxa de Cancelamento</p>
                <p className="text-2xl font-bold text-orange-400 mt-1">{overview.revenue.churn_rate}%</p>
                <p className="text-slate-500 text-xs mt-1">{overview.revenue.cancelled_this_month} cancelamentos</p>
              </div>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Plan Distribution */}
              <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-slate-300 mb-4">Distribuição por Plano</h3>
                <div className="space-y-3">
                  {Object.entries(overview.users.by_plan).map(([plan, count]) => {
                    const pct = Math.round((count / Math.max(overview.users.total, 1)) * 100)
                    const colors: Record<string, string> = {
                      free: 'bg-slate-500', pro: 'bg-green-500', enterprise: 'bg-purple-500',
                    }
                    return (
                      <div key={plan}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-slate-300 capitalize">{plan}</span>
                          <span className="text-slate-400">{count} ({pct}%)</span>
                        </div>
                        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${colors[plan] || 'bg-blue-500'}`} style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* MRR Chart */}
              <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-slate-300 mb-4">Receita Mensal (6 Meses)</h3>
                <div className="flex items-end gap-2 h-32">
                  {mrrChart.map(m => (
                    <div key={m.month} className="flex-1 flex flex-col items-center gap-1">
                      <span className="text-xs text-slate-400">{fmt(m.mrr)}</span>
                      <div
                        className="w-full bg-gradient-to-t from-purple-600 to-purple-400 rounded-t"
                        style={{ height: `${Math.max((m.mrr / maxMrr) * 100, 4)}%` }}
                      />
                      <span className="text-xs text-slate-500">{m.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Platform Stats */}
            <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Plataforma</h3>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-slate-400 text-xs">Clientes Cadastrados (Total)</p>
                  <p className="text-xl font-bold text-white">{overview.platform.total_clients}</p>
                </div>
                <div>
                  <p className="text-slate-400 text-xs">Msgs Chat (7d)</p>
                  <p className="text-xl font-bold text-white">{overview.platform.chat_messages_7d}</p>
                </div>
                <div>
                  <p className="text-slate-400 text-xs">Receita Clientes (Mês)</p>
                  <p className="text-xl font-bold text-green-400">{fmt(overview.platform.platform_revenue_month)}</p>
                </div>
              </div>
            </div>
          </>
        )}

        {/* TAB: USERS */}
        {activeTab === 'users' && (
          <>
            {/* Filters */}
            <div className="flex gap-3 items-center">
              <input
                type="text"
                value={searchTerm}
                onChange={e => { setSearchTerm(e.target.value); setPage(1) }}
                placeholder="Buscar por email ou nome..."
                className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
              <select
                value={filterPlan}
                onChange={e => { setFilterPlan(e.target.value); setPage(1) }}
                className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-purple-500"
              >
                <option value="">Todos os planos</option>
                <option value="free">Free</option>
                <option value="essencial">Essencial</option>
                <option value="profissional">Profissional</option>
                <option value="completo">Completo</option>
              </select>
              <span className="text-slate-400 text-sm">{totalUsers} Total</span>
            </div>

            {/* Users Table */}
            <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700/50 text-left">
                    <th className="px-4 py-3 text-xs text-slate-400 font-medium uppercase">Usuário</th>
                    <th className="px-4 py-3 text-xs text-slate-400 font-medium uppercase">Plano</th>
                    <th className="px-4 py-3 text-xs text-slate-400 font-medium uppercase">Status</th>
                    <th className="px-4 py-3 text-xs text-slate-400 font-medium uppercase">Cadastro</th>
                    <th className="px-4 py-3 text-xs text-slate-400 font-medium uppercase">Último Login</th>
                    <th className="px-4 py-3 text-xs text-slate-400 font-medium uppercase">Req/Hoje</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => {
                    const planColors: Record<string, string> = {
                      free: 'bg-slate-600 text-slate-200',
                      essencial: 'bg-blue-600/30 text-blue-300',
                      profissional: 'bg-green-600/30 text-green-300',
                      completo: 'bg-purple-600/30 text-purple-300',
                      pro: 'bg-green-600/30 text-green-300',
                      enterprise: 'bg-purple-600/30 text-purple-300',
                    }
                    return (
                      <tr key={u.id} className="border-b border-slate-700/30 hover:bg-slate-700/20">
                        <td className="px-4 py-3">
                          <p className="text-sm text-white font-medium">{u.full_name}</p>
                          <p className="text-xs text-slate-400">{u.email}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${planColors[u.plan] || 'bg-slate-600'}`}>
                            {u.plan}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs ${u.status === 'active' ? 'text-green-400' : 'text-red-400'}`}>
                            {u.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-400">
                          {u.created_at ? new Date(u.created_at).toLocaleDateString('pt-BR') : '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-400">
                          {u.last_login ? new Date(u.last_login).toLocaleDateString('pt-BR') : '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-300">{u.requests_today}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 hover:bg-slate-700 disabled:opacity-40"
              >
                ← Anterior
              </button>
              <span className="text-sm text-slate-400">Página {page}</span>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={users.length < 15}
                className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 hover:bg-slate-700 disabled:opacity-40"
              >
                Próxima →
              </button>
            </div>
          </>
        )}

        {/* TAB: FEEDBACKS */}
        {activeTab === 'feedbacks' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Feedbacks dos Usuários</h2>
              <span className="text-sm text-slate-400">{feedbacks.length} registro(s)</span>
            </div>
            {feedbacksLoading ? (
              <div className="flex justify-center py-12">
                <div className="w-8 h-8 border-4 border-slate-700 border-t-purple-400 rounded-full animate-spin" />
              </div>
            ) : feedbacks.length === 0 ? (
              <div className="text-center py-12 text-slate-500">Nenhum feedback recebido ainda.</div>
            ) : (
              <div className="space-y-3">
                {feedbacks.map(fb => (
                  <div key={fb.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <div className="flex gap-0.5">
                          {[1,2,3,4,5].map(s => (
                            <span key={s} className={s <= fb.rating ? 'text-yellow-400' : 'text-slate-700'}>★</span>
                          ))}
                        </div>
                        {fb.category && (
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            fb.category === 'bug' ? 'bg-red-500/20 text-red-400' :
                            fb.category === 'sugestao' ? 'bg-blue-500/20 text-blue-400' :
                            fb.category === 'elogio' ? 'bg-green-500/20 text-green-400' :
                            'bg-orange-500/20 text-orange-400'
                          }`}>
                            {fb.category}
                          </span>
                        )}
                        {fb.agent_id && <span className="text-xs text-slate-500">Agente: {fb.agent_id}</span>}
                      </div>
                      <div className="text-xs text-slate-500">
                        <span>User #{fb.user_id}</span>
                        <span className="mx-1">·</span>
                        <span>{new Date(fb.created_at).toLocaleDateString('pt-BR')}</span>
                      </div>
                    </div>
                    {fb.message && <p className="text-sm text-slate-300">{fb.message}</p>}
                    {fb.page && <p className="text-xs text-slate-600 mt-1">Página: {fb.page}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB: SYSTEM */}
        {activeTab === 'system' && (
          <SystemHealth token={token} />
        )}
      </main>
    </div>
  )
}

function SystemHealth({ token }: { token: string | null }) {
  const [health, setHealth] = useState<AdminHealthData | null>(null)

  useEffect(() => {
    if (token) {
      axios.get(apiUrl('/api/admin/health'), { headers: { Authorization: `Bearer ${token}` } })
        .then(r => setHealth(r.data))
        .catch((err) => console.warn('Falha ao carregar saúde do sistema:', err?.message))
    }
  }, [token])

  if (!health) return <div className="flex items-center gap-2 text-slate-400"><div className="w-5 h-5 border-2 border-slate-600 border-t-green-400 rounded-full animate-spin" /> Carregando...</div>

  return (
    <div className="space-y-4">
      <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Saúde do Sistema</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-slate-400 text-xs">Status</p>
            <p className={`text-lg font-bold ${health.status === 'healthy' ? 'text-green-400' : 'text-orange-400'}`}>
              {health.status === 'healthy' ? '✅ Saudável' : '⚠️ Degradado'}
            </p>
          </div>
          <div>
            <p className="text-slate-400 text-xs">Banco de Dados</p>
            <p className={`text-lg font-bold ${health.database?.connected ? 'text-green-400' : 'text-red-400'}`}>
              {health.database?.connected ? '✅ Conectado' : '❌ Offline'}
            </p>
          </div>
          <div>
            <p className="text-slate-400 text-xs">Tamanho DB</p>
            <p className="text-lg font-bold text-white">{health.database?.size_mb} MB</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs">Ambiente</p>
            <p className="text-lg font-bold text-white capitalize">{health.environment}</p>
          </div>
        </div>
      </div>
      <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-2">Informações</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Python</span>
            <span className="text-slate-300 font-mono text-xs">{health.python_version}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">DB Path</span>
            <span className="text-slate-300 font-mono text-xs truncate max-w-xs">{health.database?.path}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Verificação</span>
            <span className="text-slate-300 font-mono text-xs">{health.checked_at ? new Date(health.checked_at).toLocaleString('pt-BR') : '—'}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
