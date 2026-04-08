'use client'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Plus, Trash2, TrendingUp, TrendingDown, ArrowLeftRight } from 'lucide-react'

const CATEGORIES = ['Sales', 'Services', 'Rent', 'Salaries', 'Utilities', 'Marketing', 'Tax', 'Other']

export default function TransactionsPage() {
  const [txs, setTxs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ date: today(), amount: '', type: 'income', category: '', description: '', reference: '', currency: 'USD' })
  const [saving, setSaving] = useState(false)

  function load() {
    setLoading(true)
    api.getTransactions().then(d => { setTxs(d); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function addTx(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      await api.createTransaction({ ...form, amount: parseFloat(form.amount) })
      setShowForm(false)
      setForm({ date: today(), amount: '', type: 'income', category: '', description: '', reference: '', currency: 'USD' })
      load()
    } catch (err: any) {
      alert(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function deleteTx(id: string) {
    if (!confirm('Delete this transaction?')) return
    await api.deleteTransaction(id)
    setTxs(prev => prev.filter(t => t.id !== id))
  }

  const typeIcon = (t: string) => t === 'income' ? <TrendingUp size={14} className="text-green-400" />
    : t === 'expense' ? <TrendingDown size={14} className="text-red-400" />
    : <ArrowLeftRight size={14} className="text-blue-400" />

  const typeColor = (t: string) => t === 'income' ? 'text-green-400' : t === 'expense' ? 'text-red-400' : 'text-blue-400'

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-zaki-text">Transactions</h1>
        <button onClick={() => setShowForm(v => !v)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg transition-colors">
          <Plus size={16} /> Add Transaction
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <form onSubmit={addTx} className="bg-zaki-card border border-zaki-border rounded-xl p-5 grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-zaki-muted mb-1">Date</label>
            <input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
              className="w-full bg-zaki-surface border border-zaki-border rounded-lg px-3 py-2 text-zaki-text text-sm focus:outline-none focus:border-purple-500" required />
          </div>
          <div>
            <label className="block text-xs text-zaki-muted mb-1">Amount</label>
            <input type="number" step="0.01" value={form.amount} placeholder="0.00"
              onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
              className="w-full bg-zaki-surface border border-zaki-border rounded-lg px-3 py-2 text-zaki-text text-sm focus:outline-none focus:border-purple-500" required />
          </div>
          <div>
            <label className="block text-xs text-zaki-muted mb-1">Type</label>
            <select value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
              className="w-full bg-zaki-surface border border-zaki-border rounded-lg px-3 py-2 text-zaki-text text-sm focus:outline-none focus:border-purple-500">
              <option value="income">Income</option>
              <option value="expense">Expense</option>
              <option value="transfer">Transfer</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-zaki-muted mb-1">Category</label>
            <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
              className="w-full bg-zaki-surface border border-zaki-border rounded-lg px-3 py-2 text-zaki-text text-sm focus:outline-none focus:border-purple-500">
              <option value="">— Select —</option>
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-zaki-muted mb-1">Description</label>
            <input type="text" value={form.description} placeholder="Optional description"
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              className="w-full bg-zaki-surface border border-zaki-border rounded-lg px-3 py-2 text-zaki-text text-sm focus:outline-none focus:border-purple-500" />
          </div>
          <div className="col-span-2 flex gap-2 justify-end">
            <button type="button" onClick={() => setShowForm(false)}
              className="px-4 py-2 text-sm text-zaki-muted hover:text-zaki-text border border-zaki-border rounded-lg transition-colors">Cancel</button>
            <button type="submit" disabled={saving}
              className="px-4 py-2 text-sm bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-lg transition-colors disabled:opacity-50">
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      )}

      {/* Table */}
      <div className="bg-zaki-card border border-zaki-border rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-zaki-muted">Loading…</div>
        ) : txs.length === 0 ? (
          <div className="p-8 text-center text-zaki-muted">
            No transactions yet. Add one above or <a href="/upload" className="text-purple-400 hover:underline">upload a CSV</a>.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-zaki-border">
              <tr className="text-xs text-zaki-muted">
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-left px-4 py-3">Description</th>
                <th className="text-left px-4 py-3">Category</th>
                <th className="text-left px-4 py-3">Type</th>
                <th className="text-right px-4 py-3">Amount</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zaki-border">
              {txs.map(tx => (
                <tr key={tx.id} className="hover:bg-zaki-surface/50 transition-colors">
                  <td className="px-4 py-3 text-zaki-muted font-mono text-xs">{tx.date}</td>
                  <td className="px-4 py-3 text-zaki-text max-w-[200px] truncate">{tx.description || '—'}</td>
                  <td className="px-4 py-3">
                    {tx.category && <span className="px-2 py-0.5 bg-zaki-surface border border-zaki-border rounded-full text-xs text-zaki-muted">{tx.category}</span>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      {typeIcon(tx.type)}
                      <span className={`text-xs capitalize ${typeColor(tx.type)}`}>{tx.type}</span>
                    </div>
                  </td>
                  <td className={`px-4 py-3 text-right font-semibold ${typeColor(tx.type)}`}>
                    {tx.type === 'expense' ? '-' : '+'}{tx.currency} {Number(tx.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => deleteTx(tx.id)} className="text-zaki-muted hover:text-red-400 transition-colors">
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function today() {
  return new Date().toISOString().split('T')[0]
}
