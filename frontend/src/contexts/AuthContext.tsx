/**
 * AuthContext — Estado de autenticação compartilhado
 * ===================================================
 * Provê token, login, logout e metadados do usuário para toda a árvore React.
 * Substitui o antigo hook standalone useAuth que não sincronizava estado entre componentes.
 */

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { getProfile } from '../services/authService'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthState {
  token: string | null
  isLoading: boolean
  userEmail: string | null
  userPlan: string | null
  isAuthenticated: boolean
  login: (newToken: string, email?: string, plan?: string) => void
  logout: () => void
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthState | null>(null)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [userPlan, setUserPlan] = useState<string | null>(null)

  // Inicializar a partir do localStorage e validar token com o backend
  useEffect(() => {
    const savedToken = localStorage.getItem('access_token')
    const savedEmail = localStorage.getItem('user_email')
    const savedPlan = localStorage.getItem('user_plan')

    setToken(savedToken)
    setUserEmail(savedEmail)
    setUserPlan(savedPlan)

    if (savedToken) {
      // Usa authService.getProfile que passa pelo interceptor com refresh automático
      getProfile()
        .then((res) => {
          if (res.plan) {
            setUserPlan(res.plan)
            localStorage.setItem('user_plan', res.plan)
          }
          if (res.full_name) {
            localStorage.setItem('user_name', res.full_name)
          }
        })
        .catch((err) => {
          const status = err.response?.status
          if (status === 401 || status === 403) {
            // Token expirado (e refresh falhou) / conta suspensa — limpar sessão
            console.warn('[AuthContext] Token inválido após refresh, limpando sessão:', status)
            localStorage.removeItem('access_token')
            localStorage.removeItem('refresh_token')
            localStorage.removeItem('user_email')
            localStorage.removeItem('user_plan')
            localStorage.removeItem('user_name')
            localStorage.removeItem('onboarding_completed')
            setToken(null)
            setUserEmail(null)
            setUserPlan(null)
          } else {
            // Erro de rede/timeout — manter token mas logar aviso
            console.warn('[AuthContext] Erro ao validar token (mantendo sessão):', err.message || err)
          }
        })
        .finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
  }, [])

  // Login — atualiza estado React + localStorage de uma vez
  const login = useCallback((newToken: string, email?: string, plan?: string) => {
    localStorage.setItem('access_token', newToken)
    if (email) localStorage.setItem('user_email', email)
    if (plan) localStorage.setItem('user_plan', plan)

    setToken(newToken)
    if (email) setUserEmail(email)
    if (plan) setUserPlan(plan)
  }, [])

  // Logout — limpa tudo
  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_email')
    localStorage.removeItem('user_plan')
    localStorage.removeItem('user_name')
    localStorage.removeItem('onboarding_completed')
    setToken(null)
    setUserEmail(null)
    setUserPlan(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        token,
        isLoading,
        userEmail,
        userPlan,
        isAuthenticated: !!token,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth deve ser usado dentro de <AuthProvider>')
  }
  return ctx
}
