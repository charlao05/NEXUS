import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { useAuth } from './contexts/AuthContext'
import ErrorBoundary from './components/ErrorBoundary'
import CookieConsentBanner from './components/CookieConsentBanner'

// ── Lazy-loaded pages (code-splitting por rota) ──
const Dashboard = lazy(() => import('./pages/Dashboard'))
const NexusCodexLogin = lazy(() => import('./components/NexusCodexLogin'))
const PaymentSuccess = lazy(() => import('./pages/PaymentSuccess'))
const Pricing = lazy(() => import('./pages/Pricing'))
const Agents = lazy(() => import('./pages/Agents'))
const AgentConfig = lazy(() => import('./pages/AgentConfig'))
const Docs = lazy(() => import('./pages/Docs'))
const Onboarding = lazy(() => import('./pages/Onboarding'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))
const Termos = lazy(() => import('./pages/Termos'))
const Privacidade = lazy(() => import('./pages/Privacidade'))
const ResetPassword = lazy(() => import('./pages/ResetPassword'))
const DiagLogin = lazy(() => import('./pages/DiagLogin'))
const Profile = lazy(() => import('./pages/Profile'))

// Spinner reutilizado para Suspense fallback (transições de rota)
const PageSpinner = () => (
  <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
    <div className="text-center">
      <div className="w-12 h-12 rounded-full border-4 border-slate-700 border-t-green-400 animate-spin mx-auto mb-4" />
      <p className="text-slate-300">Carregando...</p>
    </div>
  </div>
)

// Planos válidos (freemium permanente + pagos)
const VALID_PLANS = new Set(['free', 'essencial', 'profissional', 'completo', 'pro', 'enterprise'])

function App() {
  const { token, isLoading, userPlan, userRole } = useAuth()

  // Admin sempre tem acesso total, independente do plano
  const isAdmin = userRole === 'admin' || userRole === 'superadmin'

  // Se temos token mas plano ainda não carregou (null), tratar como válido
  // para não redirecionar prematuramente para /pricing
  const hasValidPlan = isAdmin || userPlan === null ? !!token : VALID_PLANS.has(userPlan)

  // Verificar se precisa de onboarding
  const needsOnboarding = token && !localStorage.getItem('onboarding_completed')

  if (isLoading) {
    return <PageSpinner />
  }

  // Rotas públicas (acessíveis sem autenticação)
  const publicRoutes = (
    <>
      <Route path="/termos" element={<Termos />} />
      <Route path="/privacidade" element={<Privacidade />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/diag" element={<DiagLogin />} />
    </>
  )

  return (
    <ErrorBoundary>
    <BrowserRouter>
    <Suspense fallback={<PageSpinner />}>
      {token ? (
        needsOnboarding ? (
          // 🎯 ONBOARDING — Primeiro acesso
          <Routes>
            {publicRoutes}
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/dashboard" element={<Onboarding />} />
            <Route path="*" element={<Navigate to="/onboarding" replace />} />
          </Routes>
        ) : hasValidPlan ? (
          // ✅ COM PLANO VÁLIDO (freemium permanente ou pago)
          <Routes>
            {publicRoutes}
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/success" element={<PaymentSuccess />} />
            <Route path="/pricing" element={<Pricing />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/agents/:id" element={<AgentConfig />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/docs/:section" element={<Docs />} />
            <Route path="/docs" element={<Navigate to="/docs/quickstart" replace />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        ) : (
          // ⚠️ SEM PLANO - Redirecionar para escolha de plano
          <Routes>
            {publicRoutes}
            <Route path="/pricing" element={<Pricing />} />
            <Route path="/success" element={<PaymentSuccess />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="*" element={<Navigate to="/pricing" replace />} />
          </Routes>
        )
      ) : (
        // ❌ NÃO AUTENTICADO - Mostrar login
        <Routes>
          {publicRoutes}
          <Route path="/" element={<NexusCodexLogin />} />
          <Route path="/login" element={<NexusCodexLogin />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      )}
      <CookieConsentBanner />
    </Suspense>
    </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
