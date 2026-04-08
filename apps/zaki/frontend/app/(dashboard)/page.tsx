'use client'
import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { api } from '@/lib/api'
import {
  TrendingUp, TrendingDown, DollarSign, Activity,
  RefreshCw, ArrowUpRight, ArrowDownRight, Plus,
  Upload, Bot, Calendar, ChevronLeft, ChevronRight,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, ResponsiveContainer,
  Tooltip, BarChart, Bar, Cell, PieChart, Pie, Legend,
} from 'recharts'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const COLORS = ['#7c3aed','#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#84cc16']

function fmt(n: number) {
  if (Math.abs(n) >= 1_000_000) return `$${(n/1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000)     return `$${(n/1_000).toFixed(1)}K`
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

export default function Dashboard() {
  const now = new Date()
  const [year,  setYear]  = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [summary,  setSummary]  = useState<any>(null)
  const [recent,   setRecent]   = useState<any[]>([])
  const [loading,  setLoading]  = useState(true)
  const [user,     setUser]     = useState<any>(null)
  const [lastSync, setLastSync] = useState<Date | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, txs] = await Promise.all([
        api.getSummary(year, month),
        api.getTransactions({ limit: 8, sort: 'date_desc' }),
      ])
      setSummary(s)
      setRecent(Array.isArray(txs) ? txs.slice(0, 8) : [])
      setLastSync(new Date())
    } catch { /* silent */ }
    setLoading(false)
  }, [year, month])

  useEffect(() => {
    const u = localStorage.getItem('zaki_user')
    if (u) setUser(JSON.parse(u))
    load()
  }, [load])

  // trend data for chart (last 6 months from summary)
  const trendData: any[] = (() => {
    if (!summary?.trend) return []
    const map: Record<string, any> = {}
    for (const r of summary.trend) {
      const key = `${MONTHS[r.month - 1]} ${r.year}`
      if (!map[key]) map[key] = { name: key, income: 0, expense: 0 }
      if (r.type === 'income')  map[key].income  = r.total
      if (r.type === 'expense') map[key].expense = r.total
    }
    return Object.values(map).slice(-6)
  })()

  const catData = (summary?.categories || []).slice(0, 6).map((c: any, i: number) => ({
    ...c, fill: COLORS[i % COLORS.length],
  }))

  const income  = summary?.income  ?? 0
  const expense = summary?.expense ?? 0
  const net     = summary?.net     ?? 0
  const count   = summary?.transaction_count ?? 0

  const prevMonth = month === 1 ? { m: 12, y: year - 1 } : { m: month - 1, y: year }
  function goPrev() { if (month === 1) { setMonth(12); setYear(y => y-1) } else setMonth(m => m-1) }
  function goNext() {
    const nm = month === 12 ? 1 : month + 1
    const ny = month === 12 ? year + 1 : year
    if (ny > now.getFullYear() || (ny === now.getFullYear() && nm > now.getMonth()+1)) return
    setMonth(nm); if (month === 12) setYear(y => y+1)
  }
  const isCurrentMonth = year === now.getFullYear() && month === now.getMonth() + 1

  const Card = ({ label, value, icon: Icon, color, sub, loading: l }: any) => {
    const clr: any = {
      green:  { bg: 'bg-green-500/10',  text: 'text-green-600 dark:text-green-400',  icon: 'text-green-500' },
      red:    { bg: 'bg-red-500/10',    text: 'text-red-600 dark:text-red-400',      icon: 'text-red-500' },
      blue:   { bg: 'bg-blue-500/10',   text: 'text-blue-600 dark:text-blue-400',    icon: 'text-blue-500' },
      purple: { bg: 'bg-purple-500/10', text: 'text-purple-600 dark:text-purple-400', icon: 'text-purple-500' },
    }[color] || {}
    return (
      <div className="bg-zaki-card border border-zaki-border rounded-xl p-5 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-zaki-muted uppercase tracking-wide">{label}</span>
          <div className={`p-2 rounded-lg ${clr.bg}`}>
            <Icon size={15} className={clr.icon} />
          </div>
        </div>
        {l ? (
          <div className="h-8 w-32 bg-zaki-border rounded animate-pulse" />
        ) : (
          <div className={`text-2xl font-bold ${clr.text}`}>{value}</div>
        )}
        {sub && !l && <div className="text-xs text-zaki-muted">{sub}</div>}
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">

      {/* ── Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-zaki-text">
            {getGreeting()}, {user?.name?.split(' ')[0] || 'there'}
          </h1>
          <p className="text-zaki-muted text-sm mt-0.5">
            {user?.company ? `${user.company} · ` : ''}Financial overview
            {lastSync && ` · Updated ${lastSync.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Month navigator */}
          <div className="flex items-center gap-1 bg-zaki-card border border-zaki-border rounded-lg px-2 py-1.5">
            <button onClick={goPrev} className="p-1 hover:text-zaki-text text-zaki-muted transition-colors">
              <ChevronLeft size={15} />
            </button>
            <span className="text-sm font-medium text-zaki-text w-24 text-center">
              {MONTHS[month-1]} {year}
            </span>
            <button onClick={goNext} disabled={isCurrentMonth}
              className="p-1 hover:text-zaki-text text-zaki-muted transition-colors disabled:opacity-30">
              <ChevronRight size={15} />
            </button>
          </div>
          <button onClick={load}
            className="flex items-center gap-2 text-sm text-zaki-muted hover:text-zaki-text px-3 py-1.5 rounded-lg border border-zaki-border hover:border-purple-500 transition-all">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* ── KPI row ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card label="Total Income"    value={fmt(income)}  icon={TrendingUp}   color="green"
          sub={`${count} transaction${count !== 1 ? 's' : ''}`} loading={loading} />
        <Card label="Total Expenses"  value={fmt(expense)} icon={TrendingDown}  color="red"
          sub={expense > 0 ? `${((expense/Math.max(income,1))*100).toFixed(0)}% of income` : '—'} loading={loading} />
        <Card label="Net Cash Flow"   value={fmt(net)}     icon={DollarSign}
          color={net >= 0 ? 'blue' : 'red'}
          sub={net >= 0 ? 'Positive cash flow' : 'Negative cash flow'} loading={loading} />
        <Card label="Transactions"    value={count}        icon={Activity}      color="purple"
          sub={`${MONTHS[month-1]} ${year}`} loading={loading} />
      </div>

      {/* ── Charts row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Income vs Expense trend */}
        <div className="lg:col-span-2 bg-zaki-card border border-zaki-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-zaki-text">Income vs Expenses (6 months)</h2>
            <div className="flex items-center gap-3 text-xs text-zaki-muted">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500 inline-block"/>Income</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 inline-block"/>Expenses</span>
            </div>
          </div>
          {trendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="gi" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#10b981" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="ge" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" tick={{ fill: 'var(--zaki-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--zaki-muted)', fontSize: 11 }} axisLine={false} tickLine={false}
                  tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ background: 'var(--zaki-card)', border: '1px solid var(--zaki-border)', borderRadius: 8, color: 'var(--zaki-text)' }}
                  formatter={(v: any) => [`$${Number(v).toLocaleString()}`, '']} />
                <Area type="monotone" dataKey="income"  stroke="#10b981" fill="url(#gi)" strokeWidth={2} />
                <Area type="monotone" dataKey="expense" stroke="#ef4444" fill="url(#ge)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState icon={<TrendingUp size={28} className="text-zaki-muted" />}
              msg="No trend data yet" hint="Add transactions to see your income vs expense trend" />
          )}
        </div>

        {/* Category breakdown */}
        <div className="bg-zaki-card border border-zaki-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zaki-text mb-4">Expense Categories</h2>
          {catData.length > 0 ? (
            <div className="space-y-2.5">
              {catData.map((c: any) => {
                const pct = expense > 0 ? (c.total / expense) * 100 : 0
                return (
                  <div key={c.category}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-zaki-text font-medium truncate">{c.category || 'Uncategorized'}</span>
                      <span className="text-zaki-muted ml-2 shrink-0">{fmt(c.total)}</span>
                    </div>
                    <div className="h-1.5 bg-zaki-border rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: c.fill }} />
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyState icon={<Activity size={28} className="text-zaki-muted" />}
              msg="No expense data" hint="Upload a CSV or add transactions" />
          )}
        </div>
      </div>

      {/* ── Bottom row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Recent transactions */}
        <div className="lg:col-span-2 bg-zaki-card border border-zaki-border rounded-xl">
          <div className="flex items-center justify-between px-5 py-4 border-b border-zaki-border">
            <h2 className="text-sm font-semibold text-zaki-text">Recent Transactions</h2>
            <Link href="/transactions" className="text-xs text-purple-500 hover:text-purple-400 transition-colors">
              View all →
            </Link>
          </div>
          {loading ? (
            <div className="p-4 space-y-3">
              {[...Array(5)].map((_,i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-zaki-border animate-pulse" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3 w-40 bg-zaki-border rounded animate-pulse" />
                    <div className="h-2.5 w-24 bg-zaki-border rounded animate-pulse" />
                  </div>
                  <div className="h-3 w-16 bg-zaki-border rounded animate-pulse" />
                </div>
              ))}
            </div>
          ) : recent.length === 0 ? (
            <div className="p-8">
              <EmptyState icon={<ArrowUpRight size={28} className="text-zaki-muted" />}
                msg="No transactions yet"
                hint="Add your first transaction or upload a CSV file" />
            </div>
          ) : (
            <div className="divide-y divide-zaki-border">
              {recent.map((tx: any) => (
                <div key={tx.id} className="flex items-center gap-3 px-5 py-3 hover:bg-zaki-surface/50 transition-colors">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                    tx.type === 'income'   ? 'bg-green-500/10' :
                    tx.type === 'expense'  ? 'bg-red-500/10'   : 'bg-blue-500/10'
                  }`}>
                    {tx.type === 'income'
                      ? <ArrowUpRight   size={14} className="text-green-500" />
                      : tx.type === 'expense'
                      ? <ArrowDownRight size={14} className="text-red-500"   />
                      : <Activity       size={14} className="text-blue-500"  />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-zaki-text truncate">
                      {tx.description || tx.category || tx.type}
                    </div>
                    <div className="text-xs text-zaki-muted flex items-center gap-1.5">
                      <Calendar size={10} />
                      {tx.date}
                      {tx.category && <><span>·</span><span className="px-1.5 py-0.5 bg-zaki-surface rounded-full">{tx.category}</span></>}
                    </div>
                  </div>
                  <div className={`text-sm font-semibold shrink-0 ${
                    tx.type === 'income'  ? 'text-green-600 dark:text-green-400' :
                    tx.type === 'expense' ? 'text-red-600 dark:text-red-400'     : 'text-blue-600 dark:text-blue-400'
                  }`}>
                    {tx.type === 'expense' ? '−' : '+'}{tx.currency || 'USD'} {Number(tx.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quick actions + Summary */}
        <div className="space-y-4">
          {/* Cash flow summary */}
          <div className="bg-zaki-card border border-zaki-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-zaki-text mb-4">Cash Flow Summary</h2>
            <div className="space-y-3">
              <SummaryRow label="Total In"  value={fmt(income)}  color="text-green-600 dark:text-green-400" />
              <SummaryRow label="Total Out" value={fmt(expense)} color="text-red-600 dark:text-red-400" />
              <div className="border-t border-zaki-border pt-3">
                <SummaryRow label="Net"     value={fmt(net)}
                  color={net >= 0 ? 'text-blue-600 dark:text-blue-400' : 'text-red-600 dark:text-red-400'}
                  bold />
              </div>
              {income > 0 && (
                <div>
                  <div className="flex justify-between text-xs text-zaki-muted mb-1">
                    <span>Expense ratio</span>
                    <span>{((expense/income)*100).toFixed(0)}%</span>
                  </div>
                  <div className="h-1.5 bg-zaki-border rounded-full">
                    <div className="h-full bg-red-500 rounded-full transition-all"
                      style={{ width: `${Math.min((expense/income)*100, 100)}%` }} />
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Quick actions */}
          <div className="bg-zaki-card border border-zaki-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-zaki-text mb-3">Quick Actions</h2>
            <div className="space-y-2">
              <Link href="/transactions"
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-zaki-text hover:bg-zaki-surface border border-zaki-border hover:border-purple-500/50 transition-all">
                <Plus size={15} className="text-purple-500" /> Add Transaction
              </Link>
              <Link href="/upload"
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-zaki-text hover:bg-zaki-surface border border-zaki-border hover:border-purple-500/50 transition-all">
                <Upload size={15} className="text-blue-500" /> Upload CSV/Excel
              </Link>
              <Link href="/ai"
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-zaki-text hover:bg-zaki-surface border border-zaki-border hover:border-purple-500/50 transition-all">
                <Bot size={15} className="text-green-500" /> Ask ZAKI AI
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* ── ZAKI AI banner ── */}
      <div className="bg-gradient-to-r from-purple-600/15 to-blue-600/10 border border-purple-500/25 rounded-xl p-5 flex items-center justify-between gap-4">
        <div>
          <div className="text-zaki-text font-semibold">Ask ZAKI about your finances</div>
          <div className="text-zaki-muted text-sm mt-1">
            AI-powered analysis, forecasts, and CFO insights — voice or text
          </div>
        </div>
        <Link href="/ai"
          className="shrink-0 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg transition-colors">
          Open ZAKI AI →
        </Link>
      </div>

    </div>
  )
}

function SummaryRow({ label, value, color, bold }: { label: string; value: string; color: string; bold?: boolean }) {
  return (
    <div className="flex justify-between items-center">
      <span className={`text-sm ${bold ? 'font-semibold text-zaki-text' : 'text-zaki-muted'}`}>{label}</span>
      <span className={`text-sm font-semibold ${color}`}>{value}</span>
    </div>
  )
}

function EmptyState({ icon, msg, hint }: { icon: React.ReactNode; msg: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center gap-2">
      {icon}
      <div className="text-sm font-medium text-zaki-muted">{msg}</div>
      {hint && <div className="text-xs text-zaki-muted/70 max-w-[200px]">{hint}</div>}
    </div>
  )
}
