import { useState, useEffect, useCallback } from 'react'
import { apiUrl } from '../config/api'

export interface Notification {
  id: string
  type: string
  title: string
  message: string
  severity: 'info' | 'warning' | 'success' | 'error'
  data?: Record<string, unknown>
  timestamp: string
  read: boolean
}

export function useNotifications(token: string | null) {
  const [notifications, setNotifications] = useState<Notification[]>([])

  useEffect(() => {
    if (token) {
      // Fetch inicial de não-lidas
      fetch(apiUrl('/api/notifications/unread'), {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(r => r.json())
        .then(data => {
          if (data.notifications) {
            setNotifications(data.notifications)
          }
        })
        .catch((err) => console.warn('Falha ao buscar notificações:', err?.message))

      // Polling a cada 30s
      const interval = setInterval(() => {
        fetch(apiUrl('/api/notifications/unread'), {
          headers: { Authorization: `Bearer ${token}` },
        })
          .then(r => r.json())
          .then(data => {
            if (data.notifications) {
              setNotifications(prev => {
                const existing = new Set(prev.map(n => n.id))
                const newOnes = (data.notifications as Notification[]).filter(
                  n => !existing.has(n.id)
                )
                if (newOnes.length === 0) return prev
                return [...newOnes, ...prev].slice(0, 50)
              })
            }
          })
          .catch(() => { /* polling silencioso */ })
      }, 30000)

      return () => {
        clearInterval(interval)
      }
    }
  }, [token])

  const markRead = useCallback(async (notificationId?: string) => {
    if (!token) return
    try {
      const params = notificationId ? `?notification_id=${notificationId}` : ''
      await fetch(apiUrl(`/api/notifications/read${params}`), {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      setNotifications(prev =>
        prev.map(n =>
          notificationId ? (n.id === notificationId ? { ...n, read: true } : n) : { ...n, read: true }
        )
      )
    } catch {
      // silently fail
    }
  }, [token])

  const clearAll = useCallback(async () => {
    if (!token) return
    try {
      await fetch(apiUrl('/api/notifications/clear'), {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      setNotifications([])
    } catch {
      // silently fail
    }
  }, [token])

  const unreadCount = notifications.filter(n => !n.read).length

  return {
    notifications,
    unreadCount,
    markRead,
    clearAll,
  }
}
