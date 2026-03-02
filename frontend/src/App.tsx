import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import Dashboard from './pages/Dashboard'
import NexusCodexLogin from './components/NexusCodexLogin'
import PaymentSuccess from './pages/PaymentSuccess'
import Pricing from './pages/Pricing'
import Agents from './pages/Agents'
import AgentConfig from './pages/AgentConfig'
import Docs from './pages/Docs'
import Onboarding from './pages/Onboarding'
import AdminDashboard from './pages/AdminDashboard'
import Termos from './pages/Termos'
import Privacidade from './pages/Privacidade'
import ResetPassword from './pages/ResetPassword'
import DiagLogin from './pages/DiagLogin'
import CookieConsentBanner from './components/CookieConsentBanner'

// Planos válidos (freemium permanente + pagos)
const VALID_PLANS = new Set(['free', 'essencial', 'profissional', 'completo', 'pro', 'enterprise'])

function App() {
  const { token, isLoading, userPlan } = useAuth()

  const hasValidPlan = VALID_PLANS.has(userPlan ?? '')

  // Verificar se precisa de onboarding
  const needsOnboarding = token && !localStorage.getItem('onboarding_completed')

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="text-center">
          <div className="w-12 h-12 rounded-full border-4 border-slate-700 border-t-green-400 animate-spin mx-auto mb-4" />
          <p className="text-slate-300">Carregando...</p>
        </div>
      </div>
    )
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
    <BrowserRouter>
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
    </BrowserRouter>
  )
}

export default App
