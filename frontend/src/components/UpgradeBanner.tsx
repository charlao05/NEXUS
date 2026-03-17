/**
 * UpgradeBanner — Banner contextual de limite atingido / próximo
 * ================================================================
 * Exibe aviso quando uso ≥ 80%. Aparece SOMENTE para plano free.
 * Dismiss armazenado em sessionStorage (reseta ao fechar aba).
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, X } from 'lucide-react'
import { usePlanLimits } from '../hooks/usePlanLimits'

interface Props {
  resource: 'crm_clients' | 'invoices_per_month' | 'agent_messages_per_day'
  label: string
}

export function UpgradeBanner({ resource, label }: Props) {
  const { limits, isAtLimit, isFree, getUsagePercent } = usePlanLimits()
  const navigate = useNavigate()
  const [dismissed, setDismissed] = useState(
    sessionStorage.getItem(`banner_dismissed_${resource}`) === '1',
  )

  if (!isFree || !limits || dismissed) return null

  const info = limits.limits[resource]
  if (!info || typeof info === 'string' || Array.isArray(info)) return null
  if (info.unlimited) return null

  const percent = getUsagePercent(resource)
  if (percent < 80) return null

  const atLimit = isAtLimit(resource)

  return (
    <div
      style={{
        background: '#FFF8E1',
        border: '1px solid #FF9800',
        borderRadius: 8,
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 16,
      }}
    >
      <AlertTriangle size={18} color="#FF9800" style={{ flexShrink: 0 }} />
      <span style={{ flex: 1, fontSize: 14, color: '#5D4037' }}>
        {atLimit
          ? `Limite atingido: ${label}. Faça upgrade para continuar.`
          : `Atenção: ${info.current}/${info.max} ${label} utilizados.`}
      </span>
      <button
        onClick={() => navigate('/pricing')}
        style={{
          background: '#FF9800',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          padding: '6px 14px',
          cursor: 'pointer',
          fontSize: 13,
          fontWeight: 600,
          whiteSpace: 'nowrap',
        }}
      >
        Ver Planos
      </button>
      <button
        onClick={() => {
          sessionStorage.setItem(`banner_dismissed_${resource}`, '1')
          setDismissed(true)
        }}
        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
      >
        <X size={16} color="#999" />
      </button>
    </div>
  )
}
