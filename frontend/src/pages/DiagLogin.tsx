/**
 * Página de diagnóstico de login — Testa toda a cadeia de autenticação
 * no próprio browser para identificar exatamente onde/se algo falha.
 * 
 * Acesse: http://127.0.0.1:5173/diag
 */

import { useState } from 'react'
import { API_BASE, apiUrl } from '../config/api'

interface TestResult {
  name: string
  status: 'pending' | 'ok' | 'fail'
  detail: string
  ms?: number
}

export default function DiagLogin() {
  const [results, setResults] = useState<TestResult[]>([])
  const [running, setRunning] = useState(false)

  const addResult = (r: TestResult) =>
    setResults((prev) => [...prev.filter((p) => p.name !== r.name), r])

  async function runDiag() {
    setResults([])
    setRunning(true)

    // 1. Verificar API_BASE
    addResult({
      name: '1. API_BASE',
      status: API_BASE === '' ? 'ok' : 'fail',
      detail: API_BASE === ''
        ? `Vazio (proxy Vite ativo) ✅`
        : `"${API_BASE}" — ALERTA: deveria ser vazio em dev. O proxy pode estar bypassado!`,
    })

    // 2. Verificar VITE_API_URL
    const viteApiUrl = import.meta.env.VITE_API_URL
    addResult({
      name: '2. VITE_API_URL',
      status: !viteApiUrl ? 'ok' : 'fail',
      detail: !viteApiUrl
        ? 'Não definido (correto para dev) ✅'
        : `"${viteApiUrl}" — REMOVENDO! Causa bypass do proxy.`,
    })

    // 3. Testar health do backend via proxy
    const t3 = Date.now()
    try {
      const r = await fetch(apiUrl('/health'))
      const data = await r.json()
      addResult({
        name: '3. Backend /health',
        status: r.ok ? 'ok' : 'fail',
        detail: `Status ${r.status}: ${JSON.stringify(data)}`,
        ms: Date.now() - t3,
      })
    } catch (e: unknown) {
      addResult({
        name: '3. Backend /health',
        status: 'fail',
        detail: `ERRO: ${e instanceof Error ? e.message : String(e)}`,
        ms: Date.now() - t3,
      })
    }

    // 4. Testar login POST
    const t4 = Date.now()
    let token = ''
    try {
      const r = await fetch(apiUrl('/api/auth/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'charles.rsilva05@gmail.com',
          password: 'Admin@123',
        }),
      })
      const data = await r.json()
      if (r.ok && data.access_token) {
        token = data.access_token
        addResult({
          name: '4. POST /api/auth/login',
          status: 'ok',
          detail: `plan=${data.plan} uid=${data.user_id} token=${data.access_token.substring(0, 20)}...`,
          ms: Date.now() - t4,
        })
      } else {
        addResult({
          name: '4. POST /api/auth/login',
          status: 'fail',
          detail: `Status ${r.status}: ${JSON.stringify(data)}`,
          ms: Date.now() - t4,
        })
      }
    } catch (e: unknown) {
      addResult({
        name: '4. POST /api/auth/login',
        status: 'fail',
        detail: `ERRO DE REDE: ${e instanceof Error ? e.message : String(e)}`,
        ms: Date.now() - t4,
      })
    }

    // 5. Testar /me com token
    if (token) {
      const t5 = Date.now()
      try {
        const r = await fetch(apiUrl('/api/auth/me'), {
          headers: { Authorization: `Bearer ${token}` },
        })
        const data = await r.json()
        addResult({
          name: '5. GET /api/auth/me',
          status: r.ok ? 'ok' : 'fail',
          detail: r.ok
            ? `name=${data.full_name} plan=${data.plan} role=${data.role}`
            : `Status ${r.status}: ${JSON.stringify(data)}`,
          ms: Date.now() - t5,
        })
      } catch (e: unknown) {
        addResult({
          name: '5. GET /api/auth/me',
          status: 'fail',
          detail: `ERRO: ${e instanceof Error ? e.message : String(e)}`,
          ms: Date.now() - t5,
        })
      }
    } else {
      addResult({
        name: '5. GET /api/auth/me',
        status: 'fail',
        detail: 'Pulado — sem token do passo 4',
      })
    }

    // 6. Verificar localStorage
    const ls = {
      access_token: localStorage.getItem('access_token')?.substring(0, 20),
      user_email: localStorage.getItem('user_email'),
      user_plan: localStorage.getItem('user_plan'),
      user_name: localStorage.getItem('user_name'),
      onboarding: localStorage.getItem('onboarding_completed'),
    }
    addResult({
      name: '6. localStorage',
      status: 'ok',
      detail: JSON.stringify(ls, null, 1),
    })

    // 7. Testar authService (axios) login
    const t7 = Date.now()
    try {
      const { login } = await import('../services/authService')
      const result = await login('charles.rsilva05@gmail.com', 'Admin@123')
      addResult({
        name: '7. authService.login (axios)',
        status: 'ok',
        detail: `plan=${result.plan} uid=${result.user_id} token=${result.access_token?.substring(0, 20)}...`,
        ms: Date.now() - t7,
      })
    } catch (e: unknown) {
      let errorDetail = 'Desconhecido'
      if (e && typeof e === 'object' && 'response' in e) {
        const axErr = e as { response?: { status: number; data: unknown }; message?: string }
        errorDetail = `HTTP ${axErr.response?.status}: ${JSON.stringify(axErr.response?.data)} | ${axErr.message}`
      } else if (e instanceof Error) {
        errorDetail = e.message
      }
      addResult({
        name: '7. authService.login (axios)',
        status: 'fail',
        detail: `ERRO: ${errorDetail}`,
        ms: Date.now() - t7,
      })
    }

    // 8. Verificar URL real que será chamada
    addResult({
      name: '8. URLs resolvidas',
      status: 'ok',
      detail: `login: "${apiUrl('/api/auth/login')}" | me: "${apiUrl('/api/auth/me')}" | health: "${apiUrl('/health')}"`,
    })

    setRunning(false)
  }

  function clearAll() {
    localStorage.clear()
    setResults([])
    alert('localStorage limpo! Recarregue a página.')
  }

  return (
    <div style={{ fontFamily: 'monospace', padding: 32, background: '#111', color: '#eee', minHeight: '100vh' }}>
      <h1 style={{ color: '#4ade80', marginBottom: 8 }}>🔍 NEXUS — Diagnóstico de Login</h1>
      <p style={{ color: '#94a3b8', marginBottom: 24 }}>
        Testa toda a cadeia: API_BASE → proxy Vite → backend → JWT → /me
      </p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        <button
          onClick={runDiag}
          disabled={running}
          style={{
            background: running ? '#334155' : '#22c55e',
            color: '#fff',
            border: 'none',
            padding: '12px 24px',
            borderRadius: 8,
            cursor: running ? 'wait' : 'pointer',
            fontWeight: 'bold',
            fontSize: 16,
          }}
        >
          {running ? '⏳ Executando...' : '▶ Executar Diagnóstico'}
        </button>
        <button
          onClick={clearAll}
          style={{
            background: '#dc2626',
            color: '#fff',
            border: 'none',
            padding: '12px 24px',
            borderRadius: 8,
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: 16,
          }}
        >
          🗑 Limpar localStorage
        </button>
      </div>

      {results.map((r) => (
        <div
          key={r.name}
          style={{
            padding: 16,
            marginBottom: 8,
            borderRadius: 8,
            background: r.status === 'ok' ? '#052e16' : r.status === 'fail' ? '#450a0a' : '#1e293b',
            border: `1px solid ${r.status === 'ok' ? '#166534' : r.status === 'fail' ? '#991b1b' : '#334155'}`,
          }}
        >
          <div style={{ fontWeight: 'bold', marginBottom: 4 }}>
            {r.status === 'ok' ? '✅' : r.status === 'fail' ? '❌' : '⏳'}{' '}
            {r.name}
            {r.ms !== undefined && <span style={{ color: '#94a3b8', fontWeight: 'normal' }}> ({r.ms}ms)</span>}
          </div>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 13, color: '#cbd5e1' }}>{r.detail}</pre>
        </div>
      ))}
    </div>
  )
}
