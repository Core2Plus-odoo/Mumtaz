'use client'
import { useState, useRef, useEffect } from 'react'
import { Send, Plus, Zap } from 'lucide-react'
import { api, streamChat } from '@/lib/api'
import VoiceButton from '@/components/voice-button'

interface Message { role: 'user' | 'assistant'; content: string }

const SUGGESTIONS = [
  'What is my cash flow this month?',
  'Which expense category is highest?',
  'Forecast my revenue for next quarter',
  'What is my burn rate?',
  'Show me income vs expenses trend',
]

export default function AIPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [sessions, setSessions] = useState<any[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.getSessions().then(setSessions).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send(text?: string) {
    const msg = (text || input).trim()
    if (!msg || streaming) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setStreaming(true)
    let assistantMsg = ''
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    try {
      await streamChat(
        msg,
        sessionId,
        (chunk) => {
          assistantMsg += chunk
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1] = { role: 'assistant', content: assistantMsg }
            return updated
          })
        },
        (id) => setSessionId(id),
      )
    } catch (err) {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }
        return updated
      })
    } finally {
      setStreaming(false)
      api.getSessions().then(setSessions).catch(() => {})
    }
  }

  function newChat() {
    setMessages([])
    setSessionId(undefined)
    setInput('')
  }

  return (
    <div className="flex h-screen">
      {/* Session sidebar */}
      <div className="w-52 border-r border-zaki-border bg-zaki-surface p-3 flex flex-col gap-2 overflow-y-auto">
        <button onClick={newChat}
          className="flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed border-zaki-border text-zaki-muted hover:border-purple-500 hover:text-purple-400 text-sm transition-all w-full">
          <Plus size={14} /> New chat
        </button>
        {sessions.map(s => (
          <button key={s.id} onClick={() => {
            setSessionId(s.id)
            api.getMessages(s.id).then(msgs =>
              setMessages(msgs.map((m: any) => ({ role: m.role, content: m.content })))
            )
          }}
          className={`text-left px-3 py-2 rounded-lg text-xs text-zaki-muted hover:text-white hover:bg-zaki-card transition-all truncate ${s.id === sessionId ? 'bg-zaki-card text-white' : ''}`}>
            {s.title || 'Untitled chat'}
          </button>
        ))}
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-zaki-border flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-600 to-blue-500 flex items-center justify-center zaki-glow-sm">
            <Zap size={16} className="text-white" />
          </div>
          <div>
            <div className="font-semibold text-white text-sm">ZAKI AI CFO</div>
            <div className="text-xs text-green-400">● Online</div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-6 text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-600 to-blue-500 flex items-center justify-center zaki-glow animate-float">
                <Zap size={32} className="text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Ask ZAKI anything</h2>
                <p className="text-zaki-muted text-sm mt-1">Your AI CFO is ready to analyze your finances</p>
              </div>
              <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                {SUGGESTIONS.map(s => (
                  <button key={s} onClick={() => send(s)}
                    className="px-3 py-1.5 text-xs bg-zaki-card border border-zaki-border rounded-full text-zaki-muted hover:border-purple-500 hover:text-purple-300 transition-all">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-7 h-7 rounded-lg shrink-0 flex items-center justify-center text-xs font-bold ${
                m.role === 'assistant'
                  ? 'bg-gradient-to-br from-purple-600 to-blue-500 text-white'
                  : 'bg-zaki-border text-zaki-muted'
              }`}>
                {m.role === 'assistant' ? 'Z' : 'U'}
              </div>
              <div className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-purple-600 text-white rounded-tr-sm'
                  : 'bg-zaki-card border border-zaki-border text-zaki-text rounded-tl-sm'
              }`}>
                {m.content}
                {m.role === 'assistant' && m.content === '' && streaming && (
                  <span className="inline-block w-1 h-4 bg-purple-400 animate-pulse ml-0.5 align-middle" />
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-zaki-border">
          <div className="flex gap-2 items-end bg-zaki-card border border-zaki-border rounded-xl p-2">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
              placeholder="Ask about cash flow, expenses, forecasts…"
              rows={1}
              className="flex-1 bg-transparent text-white placeholder-zaki-muted text-sm resize-none outline-none px-2 py-1 max-h-32"
            />
            <div className="flex gap-1.5 shrink-0">
              <VoiceButton onTranscript={text => { setInput(text); }} />
              <button onClick={() => send()} disabled={!input.trim() || streaming}
                className="p-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white transition-colors">
                <Send size={16} />
              </button>
            </div>
          </div>
          <p className="text-center text-xs text-zaki-muted mt-2">ZAKI analyzes your financial data. Press Enter to send, Shift+Enter for new line.</p>
        </div>
      </div>
    </div>
  )
}
