/**
 * NEXUS — Configuração centralizada de API
 * ===========================================
 * Em dev: string vazia (Vite proxy redireciona /api → backend localhost:8000)
 * Em prod: URL completa do backend via VITE_API_URL
 *
 * Uso: import { apiUrl } from '../config/api'
 *      fetch(apiUrl('/api/auth/me'))
 */

const envUrl = import.meta.env.VITE_API_URL as string | undefined

/**
 * Base URL do backend.
 * - Dev: '' (vazio, proxy do Vite resolve)
 * - Prod: 'https://nexus-backend.onrender.com' (ou domínio customizado)
 */
export const API_BASE: string = envUrl
  ? (envUrl.startsWith('http') ? envUrl : `https://${envUrl}`)
  : ''

/**
 * Constrói URL completa para o backend.
 * @param path - caminho da API (ex: '/api/auth/me')
 * @returns URL completa em prod, relativa em dev
 */
export function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}
