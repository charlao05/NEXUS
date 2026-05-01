/**
 * usePlanLimits — Hook para consultar limites do plano e uso atual
 * =================================================================
 * Consulta GET /api/auth/my-limits e expõe helpers (isAgentAvailable, isAtLimit, isFree).
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'
import apiClient from '../services/apiClient'

interface LimitInfo {
  max: number
  current: number
  unlimited: boolean
}

export interface PlanLimits {
  plan: string
  display_name: string
  addon_clients_purchased?: boolean
  limits: {
    crm_clients: LimitInfo
    crm_suppliers: LimitInfo
    invoices_per_month: LimitInfo
    agent_messages_per_day: LimitInfo
    available_agents: string[] | '__all__'
  }
}

export function usePlanLimits() {
  const { token } = useAuth()
  // Inicializar do cache para renderização instantânea
  const [limits, setLimits] = useState<PlanLimits | null>(() => {
    try {
      const cached = localStorage.getItem('nexus_plan_limits')
      return cached ? JSON.parse(cached) : null
    } catch { return null }
  })
  const hasCacheRef = useRef(!!limits)
  const [loading, setLoading] = useState(!hasCacheRef.current)

  const refresh = useCallback(() => {
    if (!token) return
    if (!hasCacheRef.current) setLoading(true)
    apiClient.get<PlanLimits>('/api/auth/my-limits')
      .then((res) => {
        const data = res.data
        setLimits(data)
        hasCacheRef.current = true
        try { localStorage.setItem('nexus_plan_limits', JSON.stringify(data)) } catch { /* ignore */ }
      })
      .catch(() => { /* Manter cache em caso de erro */ })
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => {
    refresh()
  }, [refresh])

  const isAgentAvailable = (agentName: string): boolean => {
    if (!limits) return false
    const available = limits.limits.available_agents
    if (available === '__all__') return true
    return (available as string[]).includes(agentName)
  }

  const isAtLimit = (resource: keyof PlanLimits['limits']): boolean => {
    if (!limits) return false
    const info = limits.limits[resource]
    if (!info || typeof info === 'string' || Array.isArray(info)) return false
    if ((info as LimitInfo).unlimited) return false
    return (info as LimitInfo).current >= (info as LimitInfo).max
  }

  const getUsagePercent = (resource: 'crm_clients' | 'invoices_per_month' | 'agent_messages_per_day'): number => {
    if (!limits) return 0
    const info = limits.limits[resource] as LimitInfo
    if (!info || info.unlimited || info.max <= 0) return 0
    return Math.round((info.current / info.max) * 100)
  }

  const isFree = limits?.plan === 'free'

  return { limits, loading, isAgentAvailable, isAtLimit, getUsagePercent, isFree, refresh }
}
