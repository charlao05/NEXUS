/**
 * Auth Service - NEXUS Frontend
 * ==============================
 * Serviço de autenticação conectado ao backend FastAPI
 * Suporta refresh token automático em caso de 401
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { API_BASE } from '../config/api'

// Interface para resposta de login/signup
interface AuthResponse {
  access_token: string
  token_type: string
  user_id: string
  email: string
  plan: string
  refresh_token?: string
}

// Interface para perfil do usuário
interface UserProfile {
  user_id: string
  email: string
  full_name: string
  plan: string
  role: string
  created_at: string
  subscription_expires: string | null
  requests_used: number
  requests_limit: number
}

// Cliente axios - usa API_BASE para produção (Render domínios separados)
const authApi = axios.create({
  baseURL: `${API_BASE}/api/auth`,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// ----------- Refresh Token Logic -----------

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

// Interceptor para enviar Bearer token apenas em chamadas autenticadas
authApi.interceptors.request.use((config) => {
  const url = config.url || ''
  const publicRoutes = ['/login', '/signup', '/password-reset', '/reset-password']
  const isPublic = publicRoutes.some(r => url.startsWith(r))
  if (!isPublic) {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

// Interceptor de resposta — trata 401 com refresh automático + 403 LIMIT_REACHED
authApi.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // 403 LIMIT_REACHED — não limpar sessão
    if (error.response?.status === 403) {
      const detail = (error.response?.data as Record<string, unknown>)?.detail
      if (detail && typeof detail === 'object' && ((detail as Record<string, string>).code === 'LIMIT_REACHED' || (detail as Record<string, string>).code === 'AGENT_NOT_AVAILABLE')) {
        console.warn(`[authService] Limite atingido: ${(detail as Record<string, string>).message || (detail as Record<string, string>).code}`)
      }
      return Promise.reject(error)
    }

    // 401 — Tentar refresh token (apenas 1 vez)
    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = localStorage.getItem('refresh_token')

      // Sem refresh token ou endpoint de refresh/login — logout direto
      const url = originalRequest.url || ''
      if (!refreshToken || url.includes('/refresh') || url.includes('/login')) {
        clearSession()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // Já tentando refresh — enfileirar
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`
          }
          originalRequest._retry = true
          return authApi(originalRequest)
        })
      }

      isRefreshing = true
      originalRequest._retry = true

      try {
        const res = await axios.post<AuthResponse>(`${API_BASE}/api/auth/refresh`, {
          refresh_token: refreshToken,
        })

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
        return authApi(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        clearSession()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

// ----------- Helpers -----------

function saveTokens(data: AuthResponse) {
  if (data.access_token) {
    localStorage.setItem('access_token', data.access_token)
  }
  if (data.refresh_token) {
    localStorage.setItem('refresh_token', data.refresh_token)
  }
  if (data.email) {
    localStorage.setItem('user_email', data.email)
  }
  if (data.plan) {
    localStorage.setItem('user_plan', data.plan)
  }
}

function clearSession() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('user_email')
  localStorage.removeItem('user_plan')
  localStorage.removeItem('nexus_plan_limits')
}

/**
 * Cadastrar novo usuário
 */
export const signup = async (
  email: string, 
  password: string, 
  fullName: string,
  communicationPreference: string = 'email'
): Promise<AuthResponse> => {
  const response = await authApi.post<AuthResponse>('/signup', {
    email,
    password,
    full_name: fullName,
    communication_preference: communicationPreference
  })
  
  saveTokens(response.data)
  return response.data
}

/**
 * Login de usuário existente
 */
export const login = async (
  email: string, 
  password: string
): Promise<AuthResponse> => {
  const response = await authApi.post<AuthResponse>('/login', {
    email,
    password
  })
  
  saveTokens(response.data)
  return response.data
}

/**
 * Obter perfil do usuário autenticado
 */
export const getProfile = async (): Promise<UserProfile> => {
  const token = localStorage.getItem('access_token')
  
  if (!token) {
    throw new Error('Não autenticado')
  }
  
  // O interceptor já adiciona o header Authorization automaticamente
  const response = await authApi.get<UserProfile>('/me')
  
  return response.data
}

/**
 * Logout - limpar dados de sessão
 */
export const logout = (): void => {
  clearSession()
  window.location.href = '/login'
}

/**
 * Verificar se usuário está autenticado
 */
export const isAuthenticated = (): boolean => {
  const token = localStorage.getItem('access_token')
  return !!token
}

/**
 * Obter token atual
 */
export const getToken = (): string | null => {
  return localStorage.getItem('access_token')
}

/**
 * Alterar senha do usuário logado
 */
export const changePassword = async (
  currentPassword: string,
  newPassword: string
): Promise<{ status: string; message: string }> => {
  const response = await authApi.post<{ status: string; message: string }>('/change-password', {
    current_password: currentPassword,
    new_password: newPassword
  })
  return response.data
}

/**
 * Iniciar checkout Stripe para upgrade
 */
export const createCheckout = async (
  plan: string, 
  email?: string
): Promise<{ checkout_url: string; session_id: string }> => {
  const userEmail = email || localStorage.getItem('user_email') || ''
  
  const response = await authApi.post<{ status: string; checkout_url: string; session_id: string }>(
    '/checkout',
    { plan, email: userEmail }
  )
  
  return { 
    checkout_url: response.data.checkout_url,
    session_id: response.data.session_id
  }
}

/**
 * Iniciar checkout Stripe para addon de clientes/fornecedores extras (+10 cada por R$12,90 compra única)
 */
export const createAddonCheckout = async (
  email?: string
): Promise<{ checkout_url: string; session_id: string }> => {
  const userEmail = email || localStorage.getItem('user_email') || ''
  
  const response = await authApi.post<{ status: string; checkout_url: string; session_id: string }>(
    '/checkout/addon-clients',
    { email: userEmail }
  )
  
  return { 
    checkout_url: response.data.checkout_url,
    session_id: response.data.session_id
  }
}

export default {
  signup,
  login,
  logout,
  getProfile,
  isAuthenticated,
  getToken,
  createCheckout,
  createAddonCheckout,
  changePassword
}
