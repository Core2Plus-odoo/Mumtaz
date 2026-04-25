const BASE = process.env.NEXT_PUBLIC_API_URL || ''

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('zaki_token')
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}/api/v1${path}`, { ...init, headers })
  if (res.status === 401) {
    localStorage.removeItem('zaki_token')
    window.location.href = '/login'
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request<{ access_token: string; user: any }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  register: (data: { email: string; password: string; name: string; company?: string }) =>
    request<{ access_token: string; user: any }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  me: () => request<any>('/auth/me'),

  ssoOdoo: (odoo_url: string, db: string, email: string, password: string) =>
    request<{ access_token: string; user: any }>('/auth/sso/odoo', {
      method: 'POST',
      body: JSON.stringify({ odoo_url, db, email, password }),
    }),

  // Transactions
  getTransactions: (params?: Record<string, any>) => {
    const q = params ? '?' + new URLSearchParams(params).toString() : ''
    return request<any[]>(`/transactions/${q}`)
  },

  createTransaction: (data: any) =>
    request<any>('/transactions/', { method: 'POST', body: JSON.stringify(data) }),

  deleteTransaction: (id: string) =>
    request<void>(`/transactions/${id}`, { method: 'DELETE' }),

  getSummary: (year?: number, month?: number) => {
    const q = new URLSearchParams()
    if (year) q.set('year', String(year))
    if (month) q.set('month', String(month))
    return request<any>(`/transactions/summary?${q}`)
  },

  // Upload
  uploadCSV: (file: File) => {
    const token = getToken()
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}/api/v1/upload/csv`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    }).then(r => r.json())
  },

  getUploadTemplate: () => request<any>('/upload/template'),

  // AI
  getSessions: () => request<any[]>('/ai/sessions'),
  getMessages: (sessionId: string) => request<any[]>(`/ai/sessions/${sessionId}/messages`),

  // Voice
  transcribeAudio: (blob: Blob) => {
    const token = getToken()
    const form = new FormData()
    form.append('audio', blob, 'audio.webm')
    return fetch(`${BASE}/api/v1/voice/transcribe`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    }).then(r => r.json())
  },

  // ERP
  connectERP: (odoo_url: string, db: string, email: string, password: string) =>
    request<any>('/erp/connect', { method: 'POST', body: JSON.stringify({ odoo_url, db, email, password }) }),

  disconnectERP: () => request<any>('/erp/disconnect', { method: 'DELETE' }),

  syncERP: () => request<any>('/erp/sync', { method: 'POST' }),
}

export function streamChat(message: string, sessionId?: string, onChunk?: (text: string) => void, onSessionId?: (id: string) => void): Promise<void> {
  const token = getToken()
  return fetch(`${BASE}/api/v1/ai/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, session_id: sessionId }),
  }).then(async (res) => {
    if (!res.ok) throw new Error('Chat failed')
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value)
      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') return
        try {
          const json = JSON.parse(data)
          if (json.session_id) onSessionId?.(json.session_id)
          if (json.text) onChunk?.(json.text)
        } catch {}
      }
    }
  })
}
