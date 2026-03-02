/**
 * CookieConsentBanner — Banner LGPD de consentimento de cookies
 * ===============================================================
 * Exibido no rodapé para todos os visitantes até que aceitem.
 * Armazena a preferência em localStorage.
 */

import { useState, useEffect } from 'react'
import { Shield, X } from 'lucide-react'

const COOKIE_CONSENT_KEY = 'nexus_cookie_consent'

export default function CookieConsentBanner() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const consent = localStorage.getItem(COOKIE_CONSENT_KEY)
    if (!consent) {
      // Mostrar após 1s para não bloquear o carregamento
      const timer = setTimeout(() => setVisible(true), 1000)
      return () => clearTimeout(timer)
    }
  }, [])

  const accept = () => {
    localStorage.setItem(COOKIE_CONSENT_KEY, 'accepted')
    setVisible(false)
  }

  const decline = () => {
    localStorage.setItem(COOKIE_CONSENT_KEY, 'declined')
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-slate-900/95 backdrop-blur border-t border-slate-700 p-4 md:px-8 shadow-2xl">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-start md:items-center gap-4">
        <Shield className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5 md:mt-0" />
        <p className="text-sm text-slate-300 flex-1">
          O NEXUS utiliza cookies essenciais para autenticação e funcionamento da plataforma,
          além de cookies analíticos para melhorar sua experiência. Ao continuar navegando,
          você concorda com nossa{' '}
          <a href="/privacidade" className="text-emerald-400 hover:text-emerald-300 underline">
            Política de Privacidade
          </a>
          . Você pode recusar cookies não-essenciais.
        </p>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={decline}
            className="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-600 rounded-lg transition-colors"
          >
            Recusar
          </button>
          <button
            onClick={accept}
            className="px-4 py-2 text-sm bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-medium transition-colors"
          >
            Aceitar cookies
          </button>
          <button
            onClick={decline}
            className="p-1 text-slate-500 hover:text-white transition-colors md:hidden"
            aria-label="Fechar"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
