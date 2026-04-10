'use client'
import { useState, useRef, useEffect, useCallback, Fragment } from 'react'
import {
  Send, Zap, BarChart2, TrendingUp, TrendingDown, FileText,
  Target, AlertTriangle, Scale, Activity, DollarSign, RefreshCw,
  Copy, Check, Mic, MicOff, Loader2, Plus, ChevronDown,
  ArrowUpRight, ArrowDownRight, BookOpen, Shield, Lightbulb,
} from 'lucide-react'
import { api, streamChat } from '@/lib/api'

interface Msg { id: string; role: 'user' | 'assistant'; content: string; ts: Date }

/* ─────────────── CFO WORKFLOWS ─────────────── */
const WORKFLOWS = [
  {
    cat: 'Reports', items: [
      { icon: FileText, label: 'Monthly P&L', prompt: `As my CFO, run a full P&L analysis for this month. Include:\n## Executive Summary\n## Revenue vs Expenses (with % split)\n## Top Expense Categories\n## Gross Margin Analysis\n## Month-over-Month Changes\n## ⚠️ Risk Flags\n## ✅ CFO Recommendations (numbered)\n\nUse my actual numbers. Be specific and decisive.` },
      { icon: Activity, label: 'Cash Flow Statement', prompt: `Generate a CFO-level cash flow analysis. Cover:\n## Operating Cash Position\n## Cash In / Cash Out Summary\n## Burn Rate (monthly)\n## Liquidity Assessment\n## 90-Day Cash Trajectory\n## ⚠️ Cash Risks\n## ✅ Actions to Protect Cash` },
      { icon: TrendingUp, label: 'Revenue Report', prompt: `Analyze my revenue in depth. Provide:\n## Revenue Summary (this month + trend)\n## Revenue by Source/Category\n## Growth Rate vs Prior Month\n## Revenue Concentration Analysis\n## ⚠️ Revenue Risks\n## ✅ Growth Opportunities` },
      { icon: BookOpen, label: 'Executive Board Summary', prompt: `Write a CFO board-level executive summary of my financial position. Format for board presentation:\n## Financial Highlights (3 bullets)\n## Key Metrics\n| Metric | Current | Prior Month | Status |\n|--------|---------|-------------|--------|\n## Performance Assessment\n## Top 3 Risks\n## Strategic Recommendations` },
    ]
  },
  {
    cat: 'Analysis', items: [
      { icon: TrendingDown, label: 'Expense Deep Dive', prompt: `Conduct a thorough expense analysis. Provide:\n## Total Expense Summary\n## Top 5 Categories (with % of total and MoM change)\n## Expense Ratio Analysis\n## Unusual / Flagged Items\n## ⚠️ Cost Overruns\n## ✅ Top 5 Cost Reduction Opportunities (with $ savings estimate)` },
      { icon: AlertTriangle, label: 'Burn Rate & Runway', prompt: `Calculate my burn rate and financial runway. Include:\n## Gross Burn Rate (monthly)\n## Net Burn Rate (after revenue)\n## Cash Runway Estimate\n## Conservative / Base / Optimistic Scenarios\n## Break-even Analysis\n## ⚠️ Critical Thresholds\n## ✅ Runway Extension Actions` },
      { icon: Scale, label: 'Financial Health Score', prompt: `Score my overall financial health across 4 dimensions (each out of 25):\n## Overall Score: X / 100\n## Liquidity (X/25) — cash position, ratios\n## Profitability (X/25) — margins, net income\n## Efficiency (X/25) — expense control, ratios\n## Sustainability (X/25) — trends, concentration\n## 🔴 Critical Issues\n## 🟡 Watch Items\n## 🟢 Strengths\n## ✅ 30-60-90 Day Action Plan` },
      { icon: Lightbulb, label: 'Anomaly Detection', prompt: `Scan my financial data for anomalies and unusual patterns. Look for:\n## Unusual Transactions or Spikes\n## Expense Category Anomalies vs Historical\n## Revenue Irregularities\n## Suspicious Patterns\n## ⚠️ Items Requiring Immediate Attention\n## ✅ Recommended Actions` },
    ]
  },
  {
    cat: 'Strategy', items: [
      { icon: Target, label: 'Cost Optimization', prompt: `Identify my top cost optimization opportunities as CFO:\n## Current Cost Structure\n## Top 5 Savings Opportunities\n| Opportunity | Current Cost | Potential Saving | Effort | Timeline |\n|------------|-------------|-----------------|--------|----------|\n## Quick Wins (this week)\n## Strategic Cuts (1-3 months)\n## ✅ Priority Action List` },
      { icon: DollarSign, label: '90-Day Forecast', prompt: `Build a 90-day financial forecast based on my data:\n## Forecast Methodology\n## Month 1 (Income / Expenses / Net)\n## Month 2 (Income / Expenses / Net)\n## Month 3 (Income / Expenses / Net)\n## Key Assumptions\n## Conservative vs Optimistic Scenarios\n## ⚠️ Forecast Risks\n## ✅ Actions to Hit Targets` },
      { icon: Shield, label: 'Risk Assessment', prompt: `Assess the key financial risks in my business:\n## Risk Overview\n## Top 5 Financial Risks (ranked by severity)\n| Risk | Likelihood | Impact | Mitigation |\n|------|-----------|--------|------------|\n## Cash Flow Risks\n## Revenue Concentration Risks\n## Expense Volatility Risks\n## ✅ Risk Mitigation Plan` },
    ]
  },
]

const QUICK_ASKS = [
  'How am I doing financially this month?',
  'What is my biggest expense and can I reduce it?',
  'Am I profitable? What are my margins?',
  'What is my cash burn rate?',
  'Where should I cut costs first?',
]

/* ─────────────── MARKDOWN RENDERER ─────────────── */
function inlineFmt(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g)
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**'))
      return <strong key={i} className="font-semibold text-zaki-text">{p.slice(2, -2)}</strong>
    if (p.startsWith('*') && p.endsWith('*'))
      return <em key={i} className="italic">{p.slice(1, -1)}</em>
    if (p.startsWith('`') && p.endsWith('`'))
      return <code key={i} className="bg-zaki-surface px-1 rounded text-xs font-mono text-purple-600 dark:text-purple-400">{p.slice(1, -1)}</code>
    return <Fragment key={i}>{p}</Fragment>
  })
}

function MarkdownBlock({ text }: { text: string }) {
  const lines = text.split('\n')
  const els: React.ReactNode[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    // H2
    if (line.startsWith('## ')) {
      els.push(<h3 key={i} className="text-sm font-bold text-zaki-text mt-4 mb-1.5 pb-0.5 border-b border-zaki-border">{line.slice(3)}</h3>)
      i++; continue
    }
    // H3
    if (line.startsWith('### ')) {
      els.push(<h4 key={i} className="text-xs font-bold text-zaki-text mt-3 mb-1 uppercase tracking-wide">{line.slice(4)}</h4>)
      i++; continue
    }
    // HR
    if (line.match(/^---+$/)) {
      els.push(<hr key={i} className="border-zaki-border my-3" />)
      i++; continue
    }
    // Table
    if (line.startsWith('|')) {
      const rows: string[][] = []
      while (i < lines.length && lines[i].startsWith('|')) {
        const row = lines[i]
        if (!row.match(/^\|[-| :]+\|$/)) {
          rows.push(row.split('|').filter(Boolean).map(c => c.trim()))
        }
        i++
      }
      if (rows.length) {
        els.push(
          <div key={i} className="overflow-x-auto my-3 rounded-lg border border-zaki-border">
            <table className="w-full text-xs">
              <thead className="bg-zaki-surface">
                <tr>{rows[0].map((h, j) => <th key={j} className="px-3 py-2 text-left font-semibold text-zaki-text border-b border-zaki-border">{inlineFmt(h)}</th>)}</tr>
              </thead>
              <tbody>
                {rows.slice(1).map((row, ri) => (
                  <tr key={ri} className="border-b border-zaki-border last:border-0 hover:bg-zaki-surface/60">
                    {row.map((cell, ci) => <td key={ci} className="px-3 py-2 text-zaki-text">{inlineFmt(cell)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
      continue
    }
    // Bullet list
    if (line.match(/^[-*] /)) {
      const items: string[] = []
      while (i < lines.length && lines[i].match(/^[-*] /)) {
        items.push(lines[i].slice(2)); i++
      }
      els.push(
        <ul key={i} className="space-y-1 my-1.5 ml-3">
          {items.map((it, j) => (
            <li key={j} className="flex gap-2 text-sm text-zaki-text">
              <span className="text-purple-500 mt-1 shrink-0">•</span>
              <span>{inlineFmt(it)}</span>
            </li>
          ))}
        </ul>
      )
      continue
    }
    // Numbered list
    if (line.match(/^\d+\. /)) {
      const items: string[] = []
      while (i < lines.length && lines[i].match(/^\d+\. /)) {
        items.push(lines[i].replace(/^\d+\. /, '')); i++
      }
      els.push(
        <ol key={i} className="space-y-1 my-1.5 ml-3">
          {items.map((it, j) => (
            <li key={j} className="flex gap-2 text-sm text-zaki-text">
              <span className="text-purple-500 font-semibold shrink-0 w-4">{j + 1}.</span>
              <span>{inlineFmt(it)}</span>
            </li>
          ))}
        </ol>
      )
      continue
    }
    // Blockquote
    if (line.startsWith('> ')) {
      els.push(<blockquote key={i} className="border-l-2 border-purple-500 pl-3 text-sm text-zaki-muted italic my-2">{inlineFmt(line.slice(2))}</blockquote>)
      i++; continue
    }
    // Empty
    if (!line.trim()) { i++; continue }
    // Paragraph
    els.push(<p key={i} className="text-sm text-zaki-text leading-relaxed">{inlineFmt(line)}</p>)
    i++
  }
  return <div className="space-y-1">{els}</div>
}

/* ─────────────── FINANCIAL PULSE ─────────────── */
function fmt(n: number) {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(1)}K`
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function healthScore(income: number, expense: number, net: number): number {
  let s = 10
  if (income > 0) s += 20
  if (net > 0) s += 25
  if (income > 0 && net / income > 0.2) s += 15
  const ratio = income > 0 ? expense / income : 1
  if (ratio < 0.5) s += 30
  else if (ratio < 0.7) s += 20
  else if (ratio < 0.85) s += 10
  return Math.min(s, 100)
}

function FinancialPulse() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    api.getSummary().then(d => { setData(d); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const income  = data?.income  ?? 0
  const expense = data?.expense ?? 0
  const net     = income - expense
  const score   = healthScore(income, expense, net)
  const ratio   = income > 0 ? (expense / income) * 100 : 0
  const cats    = (data?.categories || []).slice(0, 4)

  const scoreColor = score >= 75 ? 'text-green-600 dark:text-green-400' : score >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'
  const scoreBar   = score >= 75 ? 'bg-green-500' : score >= 50 ? 'bg-amber-500' : 'bg-red-500'

  return (
    <div className="w-56 shrink-0 border-l border-zaki-border bg-zaki-surface flex flex-col overflow-y-auto">
      <div className="px-4 py-3 border-b border-zaki-border">
        <div className="text-xs font-semibold text-zaki-muted uppercase tracking-wide">Financial Pulse</div>
      </div>

      {/* This Month */}
      <div className="p-4 border-b border-zaki-border space-y-2">
        <div className="text-xs font-medium text-zaki-muted mb-2">This Month</div>
        {[
          { label: 'Income',   value: fmt(income),  color: 'text-green-600 dark:text-green-400',  icon: ArrowUpRight },
          { label: 'Expenses', value: fmt(expense), color: 'text-red-600 dark:text-red-400',    icon: ArrowDownRight },
          { label: 'Net',      value: fmt(net),     color: net >= 0 ? 'text-blue-600 dark:text-blue-400' : 'text-red-600 dark:text-red-400', icon: DollarSign },
        ].map(row => (
          <div key={row.label} className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs text-zaki-muted">
              <row.icon size={11} />
              {row.label}
            </div>
            {loading
              ? <div className="h-3 w-12 bg-zaki-border rounded animate-pulse" />
              : <span className={`text-xs font-semibold ${row.color}`}>{row.value}</span>}
          </div>
        ))}
        {!loading && income > 0 && (
          <div className="pt-1">
            <div className="flex justify-between text-xs text-zaki-muted mb-1">
              <span>Expense ratio</span><span>{ratio.toFixed(0)}%</span>
            </div>
            <div className="h-1 bg-zaki-border rounded-full">
              <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(ratio, 100)}%`, background: ratio > 80 ? '#ef4444' : ratio > 60 ? '#f59e0b' : '#10b981' }} />
            </div>
          </div>
        )}
      </div>

      {/* Health Score */}
      <div className="p-4 border-b border-zaki-border">
        <div className="text-xs font-medium text-zaki-muted mb-2">Health Score</div>
        {loading
          ? <div className="h-8 bg-zaki-border rounded animate-pulse" />
          : <>
            <div className={`text-2xl font-bold ${scoreColor}`}>{score}<span className="text-sm font-normal text-zaki-muted">/100</span></div>
            <div className="mt-1.5 h-1.5 bg-zaki-border rounded-full">
              <div className={`h-full rounded-full transition-all ${scoreBar}`} style={{ width: `${score}%` }} />
            </div>
            <div className="text-xs text-zaki-muted mt-1">
              {score >= 75 ? '🟢 Healthy' : score >= 50 ? '🟡 Needs attention' : '🔴 At risk'}
            </div>
          </>}
      </div>

      {/* Top Costs */}
      {cats.length > 0 && (
        <div className="p-4 border-b border-zaki-border">
          <div className="text-xs font-medium text-zaki-muted mb-2">Top Costs</div>
          <div className="space-y-2">
            {cats.map((c: any, i: number) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-xs text-zaki-text truncate max-w-[90px]">{c.category || 'Other'}</span>
                <span className="text-xs font-medium text-red-600 dark:text-red-400">{fmt(c.total)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alerts */}
      {!loading && (
        <div className="p-4 space-y-2">
          <div className="text-xs font-medium text-zaki-muted mb-2">Alerts</div>
          {ratio > 85 && (
            <div className="text-xs bg-red-500/10 text-red-600 dark:text-red-400 rounded-lg p-2">
              ⚠️ Expense ratio {ratio.toFixed(0)}% — dangerously high
            </div>
          )}
          {net < 0 && (
            <div className="text-xs bg-amber-500/10 text-amber-600 dark:text-amber-400 rounded-lg p-2">
              ⚠️ Negative cash flow this month
            </div>
          )}
          {net >= 0 && ratio < 60 && (
            <div className="text-xs bg-green-500/10 text-green-600 dark:text-green-400 rounded-lg p-2">
              ✅ Healthy margins this month
            </div>
          )}
          {income === 0 && (
            <div className="text-xs bg-zaki-surface text-zaki-muted rounded-lg p-2">
              No data yet — add transactions
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ─────────────── COPY BUTTON ─────────────── */
function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button onClick={copy} className="p-1 rounded text-zaki-muted hover:text-zaki-text transition-colors" title="Copy">
      {copied ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
    </button>
  )
}

/* ─────────────── MAIN PAGE ─────────────── */
export default function CFOPage() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [sessions, setSessions] = useState<any[]>([])
  const [voiceState, setVoiceState] = useState<'idle' | 'recording' | 'processing'>('idle')
  const [openCat, setOpenCat] = useState<string>('Reports')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLTextAreaElement>(null)
  const mediaRef  = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  useEffect(() => {
    api.getSessions().then(setSessions).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = useCallback(async (text?: string) => {
    const msg = (text ?? input).trim()
    if (!msg || streaming) return
    setInput('')
    const id = crypto.randomUUID()
    setMessages(prev => [...prev, { id, role: 'user', content: msg, ts: new Date() }])
    setStreaming(true)
    const aId = crypto.randomUUID()
    setMessages(prev => [...prev, { id: aId, role: 'assistant', content: '', ts: new Date() }])

    try {
      await streamChat(msg, sessionId,
        chunk => setMessages(prev => prev.map(m => m.id === aId ? { ...m, content: m.content + chunk } : m)),
        id => { setSessionId(id); api.getSessions().then(setSessions).catch(() => {}) },
      )
    } catch {
      setMessages(prev => prev.map(m => m.id === aId ? { ...m, content: 'Something went wrong. Please try again.' } : m))
    } finally {
      setStreaming(false)
    }
  }, [input, sessionId, streaming])

  function newChat() { setMessages([]); setSessionId(undefined); setInput('') }

  async function loadSession(id: string) {
    setSessionId(id)
    try {
      const msgs = await api.getMessages(id)
      setMessages(msgs.map((m: any) => ({ id: crypto.randomUUID(), role: m.role, content: m.content, ts: new Date(m.created_at) })))
    } catch {}
  }

  async function toggleVoice() {
    if (voiceState === 'recording') { mediaRef.current?.stop(); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      recorder.ondataavailable = e => chunksRef.current.push(e.data)
      recorder.onstop = async () => {
        setVoiceState('processing')
        stream.getTracks().forEach(t => t.stop())
        try {
          const { text } = await api.transcribeAudio(new Blob(chunksRef.current, { type: 'audio/webm' }))
          if (text) { send(text) }
        } catch {}
        finally { setVoiceState('idle') }
      }
      recorder.start(); mediaRef.current = recorder; setVoiceState('recording')
    } catch { alert('Microphone access denied') }
  }

  return (
    <div className="flex h-screen bg-zaki-bg overflow-hidden">

      {/* ── LEFT: CFO Playbook ── */}
      <div className="w-52 shrink-0 border-r border-zaki-border bg-zaki-surface flex flex-col overflow-y-auto">
        {/* Header */}
        <div className="px-4 py-3 border-b border-zaki-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-gradient-to-br from-purple-600 to-blue-500 flex items-center justify-center">
              <Zap size={12} className="text-white" />
            </div>
            <span className="text-xs font-bold text-zaki-text">CFO Playbook</span>
          </div>
          <button onClick={newChat} title="New analysis"
            className="p-1 rounded text-zaki-muted hover:text-purple-500 hover:bg-purple-500/10 transition-all">
            <Plus size={14} />
          </button>
        </div>

        {/* Workflows */}
        <div className="flex-1 p-2 space-y-1">
          {WORKFLOWS.map(group => (
            <div key={group.cat}>
              <button onClick={() => setOpenCat(openCat === group.cat ? '' : group.cat)}
                className="w-full flex items-center justify-between px-2 py-1.5 text-xs font-semibold text-zaki-muted hover:text-zaki-text transition-colors">
                {group.cat}
                <ChevronDown size={12} className={`transition-transform ${openCat === group.cat ? 'rotate-180' : ''}`} />
              </button>
              {openCat === group.cat && (
                <div className="space-y-0.5 mb-1">
                  {group.items.map(wf => (
                    <button key={wf.label} onClick={() => send(wf.prompt)}
                      disabled={streaming}
                      className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-left text-xs text-zaki-muted hover:text-zaki-text hover:bg-zaki-card disabled:opacity-40 transition-all">
                      <wf.icon size={12} className="text-purple-500 shrink-0" />
                      {wf.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Recent sessions */}
        {sessions.length > 0 && (
          <div className="border-t border-zaki-border p-2">
            <div className="text-xs font-semibold text-zaki-muted px-2 py-1">Recent</div>
            {sessions.slice(0, 6).map(s => (
              <button key={s.id} onClick={() => loadSession(s.id)}
                className={`w-full text-left px-2.5 py-1.5 rounded-md text-xs truncate transition-all ${
                  s.id === sessionId
                    ? 'bg-purple-600/10 text-purple-600 dark:text-purple-400'
                    : 'text-zaki-muted hover:text-zaki-text hover:bg-zaki-card'
                }`}>
                {s.title || 'Analysis'}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── CENTER: Workspace ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="px-5 py-3 border-b border-zaki-border flex items-center justify-between bg-zaki-bg">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-600 to-blue-500 flex items-center justify-center">
              <Zap size={16} className="text-white" />
            </div>
            <div>
              <div className="font-semibold text-zaki-text text-sm">ZAKI AI CFO</div>
              <div className="text-xs text-green-500 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block"/>Online · Analyzing your finances</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {streaming && (
              <div className="text-xs text-purple-500 flex items-center gap-1.5">
                <Loader2 size={12} className="animate-spin" /> Thinking…
              </div>
            )}
            <button onClick={newChat} className="text-xs text-zaki-muted hover:text-zaki-text px-2.5 py-1.5 border border-zaki-border rounded-lg transition-all hover:border-purple-500">
              New Analysis
            </button>
          </div>
        </div>

        {/* Messages / Empty State */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {messages.length === 0 ? (
            <div className="max-w-2xl mx-auto pt-6 space-y-6">
              {/* Welcome */}
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-purple-600 to-blue-500 flex items-center justify-center shrink-0 shadow-lg">
                  <Zap size={18} className="text-white" />
                </div>
                <div className="bg-zaki-card border border-zaki-border rounded-2xl rounded-tl-sm px-4 py-3 flex-1">
                  <p className="text-sm font-semibold text-zaki-text mb-1">Good to see you. I'm your AI CFO.</p>
                  <p className="text-sm text-zaki-muted">I know your numbers inside out. Ask me anything — revenue, costs, runway, forecasts — or pick a CFO analysis from the playbook.</p>
                </div>
              </div>

              {/* Quick asks */}
              <div>
                <p className="text-xs font-semibold text-zaki-muted uppercase tracking-wide mb-2">Quick Questions</p>
                <div className="grid grid-cols-1 gap-2">
                  {QUICK_ASKS.map(q => (
                    <button key={q} onClick={() => send(q)} disabled={streaming}
                      className="text-left px-3.5 py-2.5 bg-zaki-card border border-zaki-border rounded-xl text-sm text-zaki-text hover:border-purple-500 hover:bg-purple-500/5 disabled:opacity-40 transition-all">
                      {q}
                    </button>
                  ))}
                </div>
              </div>

              {/* CFO Workflow buttons */}
              <div>
                <p className="text-xs font-semibold text-zaki-muted uppercase tracking-wide mb-2">CFO Analyses</p>
                <div className="grid grid-cols-2 gap-2">
                  {WORKFLOWS.flatMap(g => g.items).slice(0, 6).map(wf => (
                    <button key={wf.label} onClick={() => send(wf.prompt)} disabled={streaming}
                      className="flex items-center gap-2.5 px-3.5 py-3 bg-zaki-card border border-zaki-border rounded-xl text-sm text-left hover:border-purple-500 hover:bg-purple-500/5 disabled:opacity-40 transition-all">
                      <div className="w-7 h-7 rounded-lg bg-purple-500/10 flex items-center justify-center shrink-0">
                        <wf.icon size={13} className="text-purple-500" />
                      </div>
                      <span className="text-zaki-text text-xs font-medium">{wf.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            messages.map(m => (
              <div key={m.id} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                {/* Avatar */}
                <div className={`w-8 h-8 rounded-lg shrink-0 flex items-center justify-center text-xs font-bold ${
                  m.role === 'assistant'
                    ? 'bg-gradient-to-br from-purple-600 to-blue-500 text-white shadow-md'
                    : 'bg-zaki-surface border border-zaki-border text-zaki-muted'
                }`}>
                  {m.role === 'assistant' ? <Zap size={14} className="text-white" /> : 'U'}
                </div>

                {/* Bubble */}
                <div className={`max-w-[78%] rounded-2xl ${
                  m.role === 'user'
                    ? 'bg-purple-600 text-white px-4 py-2.5 rounded-tr-sm'
                    : 'bg-zaki-card border border-zaki-border px-4 py-3 rounded-tl-sm flex-1'
                }`}>
                  {m.role === 'user'
                    ? <p className="text-sm">{m.content}</p>
                    : m.content === '' && streaming
                      ? <div className="flex gap-1 items-center py-1"><div className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce"/><div className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce [animation-delay:0.1s]"/><div className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce [animation-delay:0.2s]"/></div>
                      : <>
                          <MarkdownBlock text={m.content} />
                          <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-zaki-border">
                            <span className="text-xs text-zaki-muted">{m.ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            <CopyBtn text={m.content} />
                          </div>
                        </>
                  }
                </div>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-zaki-border bg-zaki-bg">
          <div className="max-w-3xl mx-auto">
            <div className="flex gap-2 items-end bg-zaki-card border border-zaki-border rounded-2xl p-2 focus-within:border-purple-500 transition-colors">
              <textarea ref={inputRef} value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder="Ask your CFO anything… revenue, costs, forecast, risks"
                rows={1}
                className="flex-1 bg-transparent text-zaki-text placeholder-zaki-muted text-sm resize-none outline-none px-2 py-1.5 max-h-32"
              />
              <div className="flex gap-1.5 shrink-0 pb-0.5">
                <button onClick={toggleVoice}
                  className={`p-2.5 rounded-xl border transition-all ${
                    voiceState === 'recording' ? 'bg-red-500 border-red-500 text-white animate-pulse'
                    : voiceState === 'processing' ? 'bg-purple-600/20 border-purple-600 text-purple-400'
                    : 'bg-zaki-surface border-zaki-border text-zaki-muted hover:border-purple-500 hover:text-purple-400'
                  }`}>
                  {voiceState === 'processing' ? <Loader2 size={16} className="animate-spin" />
                   : voiceState === 'recording' ? <MicOff size={16} />
                   : <Mic size={16} />}
                </button>
                <button onClick={() => send()} disabled={!input.trim() || streaming}
                  className="p-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white transition-all">
                  <Send size={16} />
                </button>
              </div>
            </div>
            <p className="text-center text-xs text-zaki-muted mt-2">
              Enter to send · Shift+Enter for new line · 🎙️ Voice input supported
            </p>
          </div>
        </div>
      </div>

      {/* ── RIGHT: Financial Pulse ── */}
      <FinancialPulse />
    </div>
  )
}
