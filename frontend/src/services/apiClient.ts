/**
 * apiClient — Cliente axios unificado para chamadas autenticadas
 * ================================================================
 * Responsável por:
 * - Injetar Authorization: Bearer <access_token> em rotas privadas.
 * - Em 401, tentar refresh-token automaticamente (1 retry por request).
 * - Enfileirar requests concorrentes durante um refresh em andamento.
 * - Em falha de refresh, limpar sessão e redirecionar para /login.
 *
 * NÃO usar este cliente para fluxos puros de auth (signup/login/refresh
 * em si). Esses ficam em authService.ts via authApi.
 */
import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import { API_BASE } from '../config/api'

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------
interface RefreshResponse {
  access_token: string
  refresh_token?: string
  token_type?: string
}

// ---------------------------------------------------------------------------
// Whitelist de rotas públicas (sem Authorization)
// ---------------------------------------------------------------------------
const PUBLIC_ROUTES = [
  '/api/auth/login',
  '/api/auth/signup',
  '/api/auth/password-reset',
  '/api/auth/reset-password',
  '/api/auth/forgot-password',
  '/api/auth/refresh',
]

function isPublicRoute(url: string | undefined): boolean {
  if (!url) return false
  // Aceita URL absoluta ou relativa
  return PUBLIC_ROUTES.some((r) => url.includes(r))
}

// ---------------------------------------------------------------------------
// Cliente axios — SEM Content-Type default (axios infere por payload)
// ---------------------------------------------------------------------------
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

// ---------------------------------------------------------------------------
// Refresh-token: estado compartilhado para fila
// ---------------------------------------------------------------------------
let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: unknown) => void
}> = []

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (token) resolve(token)
    else reject(error)
  })
  failedQueue = []
}

function clearSession() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('user_email')
  localStorage.removeItem('user_plan')
  localStorage.removeItem('user_name')
  localStorage.removeItem('user_role')
  localStorage.removeItem('onboarding_completed')
  localStorage.removeItem('nexus_plan_limits')
}

// ---------------------------------------------------------------------------
// Request interceptor — injeta Authorization em rotas privadas
// ---------------------------------------------------------------------------
apiClient.interceptors.request.use((config) => {
  const url = config.url || ''
  if (!isPublicRoute(url)) {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

// ---------------------------------------------------------------------------
// Response interceptor — refresh automático em 401
// ---------------------------------------------------------------------------
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }

    // 403 LIMIT_REACHED / AGENT_NOT_AVAILABLE — não limpar sessão
    if (error.response?.status === 403) {
      const detail = (error.response?.data as Record<string, unknown>)?.detail
      if (
        detail &&
        typeof detail === 'object' &&
        ((detail as Record<string, string>).code === 'LIMIT_REACHED' ||
          (detail as Record<string, string>).code === 'AGENT_NOT_AVAILABLE')
      ) {
        console.warn(
          `[apiClient] Limite/agente: ${
            (detail as Record<string, string>).message ||
            (detail as Record<string, string>).code
          }`
        )
      }
      return Promise.reject(error)
    }

    // 401 — tentar refresh (apenas 1x por request)
    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = localStorage.getItem('refresh_token')
      const url = originalRequest.url || ''

      // Sem refresh_token, ou já era a chamada de refresh/login → logout direto
      if (!refreshToken || isPublicRoute(url)) {
        clearSession()
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }

      // Refresh já em andamento — enfileirar
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`
          }
          originalRequest._retry = true
          return apiClient(originalRequest)
        })
      }

      isRefreshing = true
      originalRequest._retry = true

      try {
        // Usar axios "puro" (não apiClient) para evitar loop de interceptor
        const res = await axios.post<RefreshResponse>(
          `${API_BASE}/api/auth/refresh`,
          { refresh_token: refreshToken }
        )
        const newAccessToken = res.data.access_token
        const newRefreshToken = res.data.refresh_token

        localStorage.setItem('access_token', newAccessToken)
        if (newRefreshToken) {
          localStorage.setItem('refresh_token', newRefreshToken)
        }

        processQueue(null, newAccessToken)

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
        }
        return apiClient(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        clearSession()
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
export { apiClient }
