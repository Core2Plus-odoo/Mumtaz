'use client'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Link2, Link2Off, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react'

export default function SettingsPage() {
  const [user, setUser] = useState<any>(null)
  const [erp, setErp] = useState({ url: '', key: '' })
  const [erpStatus, setErpStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle')
  const [erpMsg, setErpMsg] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<any>(null)

  useEffect(() => {
    api.me().then(u => {
      setUser(u)
      if (u.has_erp) setErpStatus('connected')
      if (u.erp_url) setErp(e => ({ ...e, url: u.erp_url }))
    }).catch(() => {})
  }, [])

  async function connectERP(e: React.FormEvent) {
    e.preventDefault()
    setErpStatus('connecting')
    setErpMsg('')
    try {
      await api.connectERP(erp.url, erp.key)
      setErpStatus('connected')
      setErpMsg('Connected successfully!')
      api.me().then(setUser)
    } catch (err: any) {
      setErpStatus('error')
      setErpMsg(err.message)
    }
  }

  async function disconnectERP() {
    if (!confirm('Disconnect from Mumtaz ERP?')) return
    await api.disconnectERP()
    setErpStatus('idle')
    setErpMsg('')
    api.me().then(setUser)
  }

  async function syncERP() {
    setSyncing(true)
    setSyncResult(null)
    try {
      const res = await api.syncERP()
      setSyncResult(res)
    } catch (err: any) {
      setSyncResult({ error: err.message })
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-xl font-bold text-zaki-text">Settings</h1>

      {/* Profile */}
      <Section title="Profile">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <KV label="Name" value={user?.name} />
          <KV label="Email" value={user?.email} />
          <KV label="Company" value={user?.company || '—'} />
        </div>
      </Section>

      {/* ERP Integration */}
      <Section title="Mumtaz ERP Integration" subtitle="Connect your ERP to sync invoices, bills and contacts">
        {erpStatus === 'connected' ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-green-400 text-sm">
              <CheckCircle size={16} /> Connected to {user?.erp_url || 'Mumtaz ERP'}
            </div>
            <div className="flex gap-2">
              <button onClick={syncERP} disabled={syncing}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50">
                <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
                {syncing ? 'Syncing…' : 'Sync Now'}
              </button>
              <button onClick={disconnectERP}
                className="flex items-center gap-2 px-4 py-2 border border-red-500/30 text-red-400 hover:bg-red-500/10 text-sm font-medium rounded-lg transition-colors">
                <Link2Off size={14} /> Disconnect
              </button>
            </div>
            {syncResult && (
              <div className={`p-3 rounded-lg text-sm ${syncResult.error ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400'}`}>
                {syncResult.error ? syncResult.error : `Synced ${syncResult.synced} transactions`}
              </div>
            )}
          </div>
        ) : (
          <form onSubmit={connectERP} className="space-y-3">
            <div>
              <label className="block text-xs text-zaki-muted mb-1">Mumtaz ERP URL</label>
              <input type="url" value={erp.url} onChange={e => setErp(v => ({ ...v, url: e.target.value }))}
                placeholder="https://app.mumtaz.digital" required
                className="w-full bg-zaki-surface border border-zaki-border rounded-lg px-3 py-2 text-zaki-text text-sm focus:outline-none focus:border-purple-500" />
            </div>
            <div>
              <label className="block text-xs text-zaki-muted mb-1">API Key</label>
              <input type="password" value={erp.key} onChange={e => setErp(v => ({ ...v, key: e.target.value }))}
                placeholder="Your Mumtaz API key" required
                className="w-full bg-zaki-surface border border-zaki-border rounded-lg px-3 py-2 text-zaki-text text-sm focus:outline-none focus:border-purple-500" />
              <p className="text-xs text-zaki-muted mt-1">Find your API key in Mumtaz ERP → Settings → Technical → API Keys</p>
            </div>
            {erpMsg && (
              <div className={`flex items-center gap-2 text-sm ${erpStatus === 'error' ? 'text-red-400' : 'text-green-400'}`}>
                {erpStatus === 'error' ? <AlertCircle size={14} /> : <CheckCircle size={14} />}
                {erpMsg}
              </div>
            )}
            <button type="submit" disabled={erpStatus === 'connecting'}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50">
              <Link2 size={14} />
              {erpStatus === 'connecting' ? 'Connecting…' : 'Connect ERP'}
            </button>
          </form>
        )}
      </Section>
    </div>
  )
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="bg-zaki-card border border-zaki-border rounded-xl p-5 space-y-4">
      <div>
        <h2 className="font-semibold text-zaki-text">{title}</h2>
        {subtitle && <p className="text-xs text-zaki-muted mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  )
}

function KV({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <div className="text-xs text-zaki-muted mb-0.5">{label}</div>
      <div className="text-zaki-text text-sm">{value || '—'}</div>
    </div>
  )
}
