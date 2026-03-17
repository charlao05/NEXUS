import { useState, useRef, useEffect } from 'react'
import type { Notification } from '../hooks/useNotifications'

interface NotificationBellProps {
  notifications: Notification[]
  unreadCount: number
  onMarkRead: (id?: string) => void
  onClearAll: () => void
}

const SEVERITY_STYLES: Record<string, { bg: string; border: string; icon: string }> = {
  info: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', icon: 'ℹ️' },
  warning: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', icon: '⚠️' },
  success: { bg: 'bg-green-500/10', border: 'border-green-500/30', icon: '✅' },
  error: { bg: 'bg-red-500/10', border: 'border-red-500/30', icon: '🔴' },
}

export default function NotificationBell({
  notifications,
  unreadCount,
  onMarkRead,
  onClearAll,
}: NotificationBellProps) {
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Fechar ao clicar fora
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts)
      const now = new Date()
      const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000)
      if (diffMin < 1) return 'agora'
      if (diffMin < 60) return `${diffMin}min`
      if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h`
      return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
    } catch {
      return ''
    }
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 text-slate-400 hover:text-white transition-colors"
        title="Notificações"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 rounded-full text-[10px] font-bold flex items-center justify-center text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 max-h-[420px] overflow-y-auto bg-slate-800 border border-slate-700 rounded-xl shadow-2xl z-50">
          {/* Header */}
          <div className="sticky top-0 bg-slate-800 border-b border-slate-700/50 px-4 py-2.5 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Notificações</h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={() => onMarkRead()}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  Marcar Lidas
                </button>
              )}
              {notifications.length > 0 && (
                <button
                  onClick={onClearAll}
                  className="text-xs text-slate-500 hover:text-slate-300"
                >
                  Limpar
                </button>
              )}
            </div>
          </div>

          {/* List */}
          {notifications.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-sm">
              Nenhuma Notificação
            </div>
          ) : (
            <div className="divide-y divide-slate-700/30">
              {notifications.map(n => {
                const style = SEVERITY_STYLES[n.severity] || SEVERITY_STYLES.info
                return (
                  <div
                    key={n.id}
                    onClick={() => !n.read && onMarkRead(n.id)}
                    className={`px-4 py-3 cursor-pointer hover:bg-slate-700/30 transition-colors ${
                      !n.read ? 'bg-slate-700/10' : ''
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      <span className="text-base mt-0.5">{style.icon}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <p className={`text-sm font-medium ${!n.read ? 'text-white' : 'text-slate-400'}`}>
                            {n.title}
                          </p>
                          <span className="text-[10px] text-slate-500 whitespace-nowrap">
                            {formatTime(n.timestamp)}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">{n.message}</p>
                      </div>
                      {!n.read && (
                        <span className="w-2 h-2 bg-blue-500 rounded-full mt-1.5 flex-shrink-0" />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
