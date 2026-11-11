// The conversation drawer: talk to Zayan or Layla from any screen, by voice
// or text. The ElevenLabs conversational agent carries the voice and the
// turn-taking; every fact it speaks comes from a client tool that runs here,
// in the browser, against the Jawhar API as the signed-in user. Restricted
// clients are filtered before anything leaves for the model. Without a
// configured voice agent the drawer falls back to the server's text chat.
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { Conversation as Convo, Mode, Status } from '@elevenlabs/client';
import { api, type ChatMessage } from '../lib/api';
import { useT } from '../lib/i18n';

export const AGENTS = {
  zayan: { name: 'Zayan', role: 'coordinator', portrait: '/app/agents/zayan.webp' },
  layla: { name: 'Layla', role: 'client & retail', portrait: '/app/agents/layla.webp' },
} as const;
export type AgentKey = keyof typeof AGENTS;

export function Portrait({ agent, size = 40, talking = false }: { agent: AgentKey; size?: number; talking?: boolean }) {
  const a = AGENTS[agent];
  return <img className={`portrait ${talking ? 'talking' : ''}`} src={a.portrait} alt={`${a.name}, AI-generated portrait`} width={size} height={size} />;
}

const SCREENS: Record<string, string> = {
  today: '/', agents: '/agents', clients: '/clients', counter: '/counter', pieces: '/pieces',
  pipeline: '/pipeline', rates: '/rates', documents: '/documents', invoices: '/invoices', 'old-gold': '/old-gold',
};

/** The client tools the voice agent may call. Every one runs as the signed-in
 *  user through the API; what goes back to the model is text with no
 *  restricted client in it. */
function makeTools(nav: (to: string) => void, note: (m: ChatMessage) => void) {
  const say = (tool: string, text: string) => { note({ role: 'agent', text, tool }); return text; };
  return {
    jawhar_get_rate: async () => {
      const { rate: r } = await api.rateCurrent();
      if (!r) return say('rate', 'No approved rate is in force; nothing can be priced until a checker approves one.');
      return say('rate', `Approved 24K rate: ${r.rate_per_gram} ${r.currency} per gram, approved by ${r.approved_by?.name ?? 'a checker'} at ${r.approved_at ?? r.effective_at}.`);
    },
    jawhar_get_brief: async () => {
      const b = await api.aiBrief(true);
      if (b.refused) return say('brief', b.message ?? b.refused);
      const q = b.queue.map((x, i) => `${i + 1}. ${x.title} — ${x.next ?? ''} (${x.owner})`).join('\n');
      return say('brief', `${b.sentences.join(' ')}\nWaiting:\n${q || 'nothing'}\nAs of ${b.as_of}.`);
    },
    jawhar_get_queue: async () => {
      const r = await api.aiQueue(true);
      if (r.refused) return say('queue', r.message ?? r.refused);
      return say('queue', r.items.length ? r.items.map((x, i) => `${i + 1}. ${x.title} — ${x.next ?? ''} (${x.owner})`).join('\n') : 'Nothing waits for a decision.');
    },
    jawhar_find_client: async ({ query }: { query: string }) => {
      const r = await api.clients({ q: query, limit: 5 });
      const items = r.items.filter((c) => !c.restricted);
      if (!items.length) return say('find_client', 'No client found by that name; a Private or Royal client would not be listed here.');
      return say('find_client', items.map((c) => `${c.name} (id ${c.id}, ${c.tier || 'standard'}${c.city ? ', ' + c.city : ''}${c.next_occasion ? ', ' + c.next_occasion.kind + ' in ' + c.next_occasion.in_days + ' days' : ''})`).join('; '));
    },
    jawhar_prepare_tray: async ({ client_name, intent, budget }: { client_name: string; intent?: string; budget?: number }) => {
      const found = (await api.clients({ q: client_name, limit: 5 })).items.filter((c) => !c.restricted);
      if (found.length !== 1) return say('tray', found.length ? 'Several clients match; ask which one.' : 'No such client I may prepare for.');
      const out = await api.aiLaylaTray({ client_id: found[0].id, intent, budget, limit: 3 });
      if (out.refused) return say('tray', out.message ?? out.refused);
      const pieces = out.tray.lines?.map((l) => `${l.piece.serial} ${l.piece.product?.name ?? ''} ${l.piece.karat}K at ${l.price}`).join('; ');
      note({ role: 'agent', text: `${out.tray.name} prepared for ${found[0].name}.`, tool: 'tray', links: [{ label: 'Open the tray', to: `/trays/${out.tray.id}` }, { label: 'Review in the inbox', to: `/agents?draft=${out.draft.id}` }] });
      return `Tray ${out.tray.name} (tray id ${out.tray.id}, draft id ${out.draft.id}) prepared for ${found[0].name}: ${pieces}. All in stock, reasons attached; it waits in the inbox for review.`;
    },
    jawhar_draft_followup: async ({ client_name, context, channel }: { client_name: string; context?: string; channel?: string }) => {
      const found = (await api.clients({ q: client_name, limit: 5 })).items.filter((c) => !c.restricted);
      if (found.length !== 1) return say('followup', found.length ? 'Several clients match; ask which one.' : 'No such client I may draft for.');
      const out = await api.aiLaylaFollowup({ client_id: found[0].id, context, channel });
      if (out.refused) return say('followup', out.message ?? out.refused);
      note({ role: 'agent', text: `Draft ${out.draft.name} for ${found[0].name} waits in the inbox.`, tool: 'followup', links: [{ label: 'Review the draft', to: `/agents?draft=${out.draft.id}` }] });
      return `Draft ${out.draft.name} (draft id ${out.draft.id}, ${out.draft.channel}) for ${found[0].name} waits in the inbox for review. Text: ${out.draft.body}`;
    },
    jawhar_search_pieces: async ({ query, karat }: { query?: string; karat?: string }) => {
      const r = await api.pieces({ q: query, karat, on_hand: true, limit: 6 });
      if (!r.items.length) return say('pieces', 'Nothing in stock matches.');
      return say('pieces', r.items.map((p) => `${p.serial}: ${p.product?.name ?? ''}, ${p.karat}K, ${p.net_weight_g} g net, ${p.price_incl_vat} incl. VAT`).join('; '));
    },
    jawhar_open_screen: ({ screen, record_id }: { screen: string; record_id?: number }) => {
      let to = SCREENS[screen] ?? '/';
      if (record_id && screen === 'clients') to = `/clients/${record_id}`;
      if (record_id && screen === 'agents') to = `/agents?draft=${record_id}`;
      nav(to);
    },
  };
}

/** Open the drawer on a given agent from anywhere in the app. */
export function talkTo(agent: AgentKey) {
  window.dispatchEvent(new CustomEvent('jawhar:talk', { detail: { agent } }));
}

export default function AgentChat({ open, agent, voiceIds, onClose, onAgent }: {
  open: boolean; agent: AgentKey; voiceIds: Record<string, string>; onClose: () => void; onAgent: (a: AgentKey) => void;
}) {
  const { t, lang } = useT();
  const nav = useNavigate();
  const [threads, setThreads] = useState<Record<AgentKey, ChatMessage[]>>({ zayan: [], layla: [] });
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<Status>('disconnected');
  const [mode, setMode] = useState<Mode>('listening');
  const [notice, setNotice] = useState<string | null>(null);
  const convo = useRef<Convo | null>(null);
  const offline = useRef(false);
  const endRef = useRef<HTMLDivElement>(null);
  const msgs = threads[agent];
  const push = useCallback((a: AgentKey, m: ChatMessage) => setThreads((th) => ({ ...th, [a]: [...th[a], m] })), []);
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }); }, [msgs, open, status]);

  const end = useCallback(async () => {
    const c = convo.current; convo.current = null;
    if (c) { try { await c.endSession(); } catch { /* fine */ } }
    setStatus('disconnected');
  }, []);
  useEffect(() => () => { void end(); }, [end]);
  const switchAgent = async (a: AgentKey) => { await end(); onAgent(a); };

  const startVoice = async (textOnly = false) => {
    const agentId = voiceIds[agent];
    if (!agentId) { setNotice(t('voice_unavailable')); return; }
    setNotice(null);
    const a = agent;
    try {
      setStatus('connecting');
      const { Conversation } = await import('@elevenlabs/client');
      const session = await Conversation.startSession({
        agentId, connectionType: 'webrtc', textOnly,
        overrides: { agent: { language: lang === 'ar' ? 'ar' : 'en' } },
        clientTools: makeTools((to) => { nav(to); }, (m) => push(a, m)),
        onStatusChange: ({ status: s }) => setStatus(s),
        onModeChange: ({ mode: m }) => setMode(m),
        onMessage: ({ source, message }) => push(a, { role: source === 'user' ? 'user' : 'agent', text: message }),
        onError: (message) => setNotice(message),
        onDisconnect: () => { convo.current = null; setStatus('disconnected'); },
      });
      convo.current = session;
    } catch (e) {
      setNotice(/mic|permission|NotAllowed/i.test(String(e)) ? t('voice_mic_denied') : String(e));
      setStatus('disconnected');
    }
  };

  const send = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const q = text.trim();
    if (!q || busy) return;
    setText('');
    if (convo.current) { convo.current.sendUserMessage(q); return; }
    if (voiceIds[agent] && !offline.current) {
      // Text with the same agent and tools, no microphone.
      push(agent, { role: 'user', text: q });
      await startVoice(true);
      const c = convo.current as Convo | null;
      if (c) { c.sendUserMessage(q); return; }
      // The conversational service is out of reach: the server's text chat
      // answers from here on, with the same tools, no voice.
      offline.current = true;
      setNotice(t('voice_unavailable'));
    } else {
      push(agent, { role: 'user', text: q });
    }
    const next = [...msgs, { role: 'user' as const, text: q }];
    setBusy(true);
    try {
      const r = await api.aiChat(agent, next.map((m) => ({ role: m.role, text: m.text })));
      push(agent, { role: 'agent', text: r.reply, links: r.links, refused: r.refused });
    } catch (err) {
      push(agent, { role: 'agent', text: (err as Error).message, refused: 'error' });
    } finally { setBusy(false); }
  };
  const chips = agent === 'zayan'
    ? ['Prepare my day', 'Gold rate', 'What is waiting for me?']
    : ['Prepare a tray for Bravo', 'Draft a follow-up to Mariam', 'What bangles do we have in 22K?'];
  const live = status === 'connected';

  if (!open) return null;
  return (
    <aside className="chat" role="dialog" aria-label={t('chat_open')}>
      <div className="chat-head">
        <div className="chat-tabs">
          {(Object.keys(AGENTS) as AgentKey[]).map((k) => (
            <button key={k} className={`chat-tab ${k === agent ? 'on' : ''}`} onClick={() => switchAgent(k)}>
              <Portrait agent={k} size={28} /><span>{AGENTS[k].name}</span>
            </button>
          ))}
        </div>
        <span className="sp" />
        <button className="btn ghost small" onClick={async () => { await end(); setThreads({ ...threads, [agent]: [] }); }}>{t('chat_clear')}</button>
        <button className="btn ghost small" onClick={async () => { await end(); onClose(); }} aria-label={t('chat_close')}>✕</button>
      </div>
      <div className="chat-body">
        <div className="chat-intro">
          <Portrait agent={agent} size={72} talking={live && mode === 'speaking'} />
          <div><b>{AGENTS[agent].name}</b><div className="small muted">{AGENTS[agent].role}</div>
            <div className="small muted">{status === 'connecting' ? t('voice_connecting') : live ? (mode === 'speaking' ? t('voice_speaking') : t('voice_listening')) : t('chat_hint')}</div>
          </div>
        </div>
        {msgs.length === 0 && <div className="chips">{chips.map((c) => <button key={c} className="chip" onClick={() => setText(c)}>{c}</button>)}</div>}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role} ${m.refused ? 'refused' : ''} ${m.tool ? 'tool' : ''}`}>
            {m.role === 'agent' && !m.tool && <Portrait agent={agent} size={26} />}
            <div className="bubble" dir="auto">
              {m.tool && <div className="small muted">⚙ {m.tool} · {t('tool_ran')}</div>}
              {m.text.split('\n').map((line, j) => <div key={j}>{line}</div>)}
              {m.links && m.links.length > 0 && (
                <div className="links">{m.links.map((l) => <Link key={l.to} to={l.to} onClick={() => { void end(); onClose(); }}>{l.label} →</Link>)}</div>
              )}
            </div>
          </div>
        ))}
        {busy && <div className="msg agent"><Portrait agent={agent} size={26} /><div className="bubble muted">…</div></div>}
        {notice && <div className="notice warn">{notice}</div>}
        <div ref={endRef} />
      </div>
      <form className="chat-input" onSubmit={send}>
        {voiceIds[agent] && (live || status === 'connecting'
          ? <button type="button" className="btn ghost mic on" onClick={end} aria-label={t('voice_stop')}>■</button>
          : <button type="button" className="btn ghost mic" onClick={() => startVoice(false)} aria-label={t('voice_start')}>🎤</button>)}
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t('chat_placeholder')} dir="auto" disabled={busy} />
        <button className="btn" disabled={busy || !text.trim()}>{t('chat_send')}</button>
      </form>
    </aside>
  );
}
