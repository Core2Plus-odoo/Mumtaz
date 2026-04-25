'use client'
import { useState } from 'react'
import { api } from '@/lib/api'

export default function LoginPage() {
  const [tab, setTab] = useState<'login' | 'register' | 'sso'>('login')
  const [form, setForm] = useState({ email: '', password: '', name: '', company: '', odoo_url: '', odoo_db: '', odoo_email: '', odoo_password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      let res: any
      if (tab === 'login') res = await api.login(form.email, form.password)
      else if (tab === 'register') res = await api.register({ email: form.email, password: form.password, name: form.name, company: form.company })
      else res = await api.ssoOdoo(form.odoo_url, form.odoo_db, form.odoo_email, form.odoo_password)

      localStorage.setItem('zaki_token', res.access_token)
      localStorage.setItem('zaki_user', JSON.stringify(res.user))
      window.location.href = '/'
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-zaki-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-600 to-blue-500 flex items-center justify-center text-white font-bold text-lg zaki-glow">Z</div>
            <span className="text-2xl font-bold text-zaki-text">ZAKI</span>
          </div>
          <p className="text-zaki-muted text-sm">Your AI CFO — financial clarity, instantly</p>
        </div>

        {/* Card */}
        <div className="bg-zaki-card border border-zaki-border rounded-2xl p-6">
          {/* Tabs */}
          <div className="flex gap-1 mb-6 bg-zaki-surface rounded-lg p-1">
            {(['login', 'register', 'sso'] as const).map(t => (
              <button key={t} onClick={() => setTab(t)}
                className={`flex-1 py-1.5 text-sm rounded-md font-medium transition-all ${
                  tab === t ? 'bg-purple-600 text-white' : 'text-zaki-muted hover:text-zaki-text'
                }`}>
                {t === 'sso' ? 'Odoo' : t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            {tab === 'register' && (
              <>
                <Input label="Full Name" value={form.name} onChange={v => set('name', v)} placeholder="Muhammad Umer" required />
                <Input label="Company" value={form.company} onChange={v => set('company', v)} placeholder="Your company name" />
              </>
            )}

            {tab === 'sso' ? (
              <>
                <Input label="Odoo URL" value={form.odoo_url} onChange={v => set('odoo_url', v)} placeholder="https://yourcompany.odoo.com" required />
                <Input label="Database" value={form.odoo_db} onChange={v => set('odoo_db', v)} placeholder="your-database" required />
                <Input label="Email" value={form.odoo_email} onChange={v => set('odoo_email', v)} placeholder="you@company.com" type="email" required />
                <Input label="Password" value={form.odoo_password} onChange={v => set('odoo_password', v)} placeholder="••••••••" type="password" required />
              </>
            ) : (
              <>
                <Input label="Email" value={form.email} onChange={v => set('email', v)} placeholder="you@company.com" type="email" required />
                <Input label="Password" value={form.password} onChange={v => set('password', v)} placeholder="••••••••" type="password" required />
              </>
            )}

            {error && <p className="text-red-400 text-sm bg-red-400/10 rounded-lg px-3 py-2">{error}</p>}

            <button type="submit" disabled={loading}
              className="w-full py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-semibold rounded-lg transition-colors">
              {loading ? 'Loading…' : tab === 'login' ? 'Sign in' : tab === 'register' ? 'Create account' : 'Sign in with Odoo'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-zaki-muted mt-4">
          Powered by <span className="text-purple-400">Mumtaz Digital</span>
        </p>
      </div>
    </div>
  )
}

function Input({ label, value, onChange, placeholder, type = 'text', required }: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string; required?: boolean
}) {
  return (
    <div>
      <label className="block text-sm text-zaki-muted mb-1">{label}</label>
      <input
        type={type} value={value} placeholder={placeholder} required={required}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-zaki-surface border border-zaki-border rounded-lg px-3 py-2 text-zaki-text placeholder-zaki-muted focus:outline-none focus:border-purple-500 transition-colors"
      />
    </div>
  )
}
