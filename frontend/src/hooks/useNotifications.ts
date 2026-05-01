import { useState, useEffect, useCallback } from 'react'
import apiClient from '../services/apiClient'

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
      apiClient.get<{ notifications?: Notification[] }>('/api/notifications/unread')
        .then(res => {
          const data = res.data
          if (data.notifications) {
            setNotifications(data.notifications)
          }
        })
        .catch((err) => console.warn('Falha ao buscar notificações:', err?.message))

      // Polling a cada 30s
      const interval = setInterval(() => {
        apiClient.get<{ notifications?: Notification[] }>('/api/notifications/unread')
          .then(res => {
            const data = res.data
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
      await apiClient.post(`/api/notifications/read${params}`)
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
      await apiClient.delete('/api/notifications/clear')
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
