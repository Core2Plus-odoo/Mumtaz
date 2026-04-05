'use client'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { TrendingUp, TrendingDown, DollarSign, Activity, RefreshCw } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip, BarChart, Bar, Cell } from 'recharts'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

export default function Dashboard() {
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [user, setUser] = useState<any>(null)

  useEffect(() => {
    const u = localStorage.getItem('zaki_user')
    if (u) setUser(JSON.parse(u))
    api.getSummary().then(s => { setSummary(s); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const trendData = summary?.trend?.reduce((acc: any[], r: any) => {
    const key = `${MONTHS[r.month - 1]} ${r.year}`
    const existing = acc.find(a => a.name === key)
    if (existing) {
      if (r.type === 'income') existing.income = r.total
      if (r.type === 'expense') existing.expense = r.total
    } else {
      acc.push({ name: key, income: r.type === 'income' ? r.total : 0, expense: r.type === 'expense' ? r.total : 0 })
    }
    return acc
  }, []).slice(-6) || []

  const cats = summary?.categories?.slice(0, 6) || []

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">
            Good {getGreeting()}, {user?.name?.split(' ')[0] || 'there'} 👋
          </h1>
          <p className="text-zaki-muted text-sm mt-0.5">Here's your financial snapshot</p>
        </div>
        <button onClick={() => { setLoading(true); api.getSummary().then(s => { setSummary(s); setLoading(false) }) }}
          className="flex items-center gap-2 text-sm text-zaki-muted hover:text-white px-3 py-1.5 rounded-lg border border-zaki-border hover:border-purple-500 transition-all">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI label="Total Income" value={summary?.income} icon={TrendingUp} color="green" loading={loading} />
        <KPI label="Total Expenses" value={summary?.expense} icon={TrendingDown} color="red" loading={loading} />
        <KPI label="Net Cash Flow" value={summary?.net} icon={DollarSign}
          color={(summary?.net ?? 0) >= 0 ? 'blue' : 'red'} loading={loading} />
        <KPI label="Transactions" value={summary?.transaction_count} icon={Activity} color="purple" loading={loading} raw />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Trend */}
        <div className="lg:col-span-2 bg-zaki-card border border-zaki-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Income vs Expenses</h2>
          {trendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="gi" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="ge" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false}
                  tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip contentStyle={{ background: '#13131f', border: '1px solid #1e1e30', borderRadius: 8 }}
                  labelStyle={{ color: '#e5e7eb' }} itemStyle={{ color: '#e5e7eb' }}
                  formatter={(v: any) => [`$${Number(v).toLocaleString()}`, '']} />
                <Area type="monotone" dataKey="income" stroke="#10b981" fill="url(#gi)" strokeWidth={2} />
                <Area type="monotone" dataKey="expense" stroke="#ef4444" fill="url(#ge)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart msg="No transaction data yet. Add transactions or upload a CSV." />
          )}
        </div>

        {/* Categories */}
        <div className="bg-zaki-card border border-zaki-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Top Expense Categories</h2>
          {cats.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={cats} layout="vertical">
                <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={false} tickLine={false}
                  tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                <YAxis type="category" dataKey="category" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} width={80} />
                <Tooltip contentStyle={{ background: '#13131f', border: '1px solid #1e1e30', borderRadius: 8 }}
                  formatter={(v: any) => [`$${Number(v).toLocaleString()}`, 'Amount']} />
                <Bar dataKey="total" radius={4}>
                  {cats.map((_: any, i: number) => (
                    <Cell key={i} fill={`hsl(${260 + i * 20}, 70%, ${55 - i * 5}%)`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart msg="No expense data yet." />
          )}
        </div>
      </div>

      {/* ZAKI CTA */}
      <div className="bg-gradient-to-r from-purple-900/40 to-blue-900/20 border border-purple-700/30 rounded-xl p-5 flex items-center justify-between">
        <div>
          <div className="text-white font-semibold">Ask ZAKI anything about your finances</div>
          <div className="text-zaki-muted text-sm mt-1">AI-powered CFO insights, forecasts, and advice</div>
        </div>
        <a href="/ai" className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap">
          Open ZAKI AI →
        </a>
      </div>
    </div>
  )
}

function KPI({ label, value, icon: Icon, color, loading, raw }: any) {
  const colors: any = {
    green: 'text-green-400 bg-green-400/10',
    red: 'text-red-400 bg-red-400/10',
    blue: 'text-blue-400 bg-blue-400/10',
    purple: 'text-purple-400 bg-purple-400/10',
  }
  return (
    <div className="bg-zaki-card border border-zaki-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-zaki-muted font-medium">{label}</span>
        <div className={`p-1.5 rounded-lg ${colors[color]}`}>
          <Icon size={14} />
        </div>
      </div>
      {loading ? (
        <div className="h-7 w-20 bg-zaki-border rounded animate-pulse" />
      ) : (
        <div className="text-xl font-bold text-white">
          {raw ? (value ?? 0).toLocaleString() : `$${(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
        </div>
      )}
    </div>
  )
}

function EmptyChart({ msg }: { msg: string }) {
  return <div className="h-48 flex items-center justify-center text-zaki-muted text-sm text-center">{msg}</div>
}

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'morning'
  if (h < 17) return 'afternoon'
  return 'evening'
}
