// The Virtual Sales Officer: a kiosk for clients, in store or on the web.
// No sign-in. Noor (an ElevenLabs conversational agent) talks and listens;
// every price she states comes from the public shelf endpoints, which carry
// no internal ids and no client data. The only write is a request, and a
// request is not a reservation: a person confirms.
import { useEffect, useRef, useState } from 'react';
import type { Conversation as Convo, Mode, Status } from '@elevenlabs/client';
import { api, type KioskPiece, type KioskRequestOut } from '../lib/api';
import { useT } from '../lib/i18n';
import { money, num, when } from '../lib/format';

const NOOR = '/app/agents/noor.webp';
const CATS = ['bangle', 'chain', 'necklace', 'ring', 'earrings', 'bracelet', 'pendant', 'set', 'coin'];
type Msg = { role: 'user' | 'agent'; text: string };
type Form = { kind: 'viewing' | 'delivery'; serial: string; name: string; phone: string; preferred_time: string; address: string; slot: 'morning' | 'afternoon'; note: string };

export default function Kiosk() {
  const { t, lang, setLang } = useT();
  const [rate, setRate] = useState<{ rate_per_gram: number; currency: string; approved_at: string } | null>(null);
  const [voiceId, setVoiceId] = useState<string | null>(null);
  const [pieces, setPieces] = useState<KioskPiece[]>([]);
  const [focus, setFocus] = useState<KioskPiece | null>(null);
  const [cat, setCat] = useState('');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [status, setStatus] = useState<Status>('disconnected');
  const [mode, setMode] = useState<Mode>('listening');
  const [text, setText] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [done, setDone] = useState<KioskRequestOut | null>(null);
  const [busy, setBusy] = useState(false);
  const convo = useRef<Convo | null>(null);
  const cur = rate?.currency ?? 'AED';

  const load = async (category = cat) => {
    const r = await api.kioskPieces({ category: category || undefined, limit: 9 });
    setPieces(r.items);
  };
  useEffect(() => {
    api.kioskRate().then((r) => setRate(r.rate)).catch(() => setRate(null));
    // The kiosk's agent id is public; it comes with the status of the app
    // when a staff session exists, and from the rate payload otherwise.
    fetch('/jawhar/public/kiosk/agent').then((r) => r.json()).then((j) => setVoiceId(j?.data?.agent_id ?? null)).catch(() => setVoiceId(null));
    void load('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { void load(cat); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [cat]);

  const push = (m: Msg) => setMsgs((ms) => [...ms.slice(-30), m]);
  const end = async () => { const c = convo.current; convo.current = null; if (c) { try { await c.endSession(); } catch { /* fine */ } } setStatus('disconnected'); };
  useEffect(() => () => { void end(); }, []);

  const tools = {
    kiosk_get_rate: async () => {
      const r = (await api.kioskRate()).rate;
      setRate(r);
      return r ? `Approved 24K rate: ${r.rate_per_gram} ${r.currency} per gram, approved ${r.approved_at}.` : 'No approved rate is in force right now.';
    },
    kiosk_search_pieces: async ({ query, category, karat, max_price }: { query?: string; category?: string; karat?: string; max_price?: number }) => {
      const r = await api.kioskPieces({ q: query, category, karat, max_price, limit: 6 });
      setPieces(r.items); setFocus(null); if (category) setCat(category);
      if (!r.items.length) return 'Nothing on the shelf matches.';
      return r.items.map((p) => `${p.serial}: ${p.design}, ${p.karat}K, ${p.net_weight_g} g net, ${p.price_incl_vat} ${p.currency} incl. VAT`).join('; ');
    },
    kiosk_show_piece: async ({ serial }: { serial: string }) => {
      try { setFocus(await api.kioskPiece(serial)); } catch { /* not on the shelf */ }
    },
    kiosk_request_viewing: async (p: { serial: string; name: string; phone: string; preferred_time?: string; note?: string }) => {
      try {
        const out = await api.kioskRequest({ kind: 'viewing', ...p, lang, channel: 'store' });
        setDone(out); return `Request ${out.reference} placed. ${out.message}`;
      } catch (e) { return `Could not place the request: ${(e as Error).message}`; }
    },
    kiosk_request_delivery: async (p: { serial: string; name: string; phone: string; address: string; slot: string; note?: string }) => {
      try {
        const out = await api.kioskRequest({ kind: 'delivery', ...p, lang, channel: 'store' });
        setDone(out); return `Request ${out.reference} placed for ${out.delivery_date} (${out.slot}). ${out.message}`;
      } catch (e) { return `Could not place the request: ${(e as Error).message}`; }
    },
  };

  const start = async (textOnly = false) => {
    if (!voiceId) { setNotice(t('voice_unavailable')); return; }
    setNotice(null); setStatus('connecting');
    try {
      const { Conversation } = await import('@elevenlabs/client');
      convo.current = await Conversation.startSession({
        agentId: voiceId, connectionType: 'webrtc', textOnly,
        overrides: { agent: { language: lang === 'ar' ? 'ar' : 'en' } },
        clientTools: tools,
        onStatusChange: ({ status: s }) => setStatus(s),
        onModeChange: ({ mode: m }) => setMode(m),
        onMessage: ({ source, message }) => push({ role: source === 'user' ? 'user' : 'agent', text: message }),
        onError: (m) => setNotice(m),
        onDisconnect: () => { convo.current = null; setStatus('disconnected'); },
      });
    } catch (e) { setNotice(/mic|permission|NotAllowed/i.test(String(e)) ? t('voice_mic_denied') : String(e)); setStatus('disconnected'); }
  };
  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = text.trim(); if (!q) return; setText('');
    if (!convo.current) { push({ role: 'user', text: q }); await start(true); }
    convo.current?.sendUserMessage(q);
  };
  const submitForm = async (e: React.FormEvent) => {
    e.preventDefault(); if (!form) return; setBusy(true); setNotice(null);
    try {
      const out = await api.kioskRequest({ ...form, lang, channel: 'store' });
      setDone(out); setForm(null);
    } catch (ex) { setNotice((ex as Error).message); } finally { setBusy(false); }
  };
  const reset = async () => { await end(); setMsgs([]); setDone(null); setForm(null); setFocus(null); setCat(''); void load(''); };
  const live = status === 'connected';

  return (
    <div className={`kiosk ${lang === 'ar' ? 'rtl' : ''}`} dir={lang === 'ar' ? 'rtl' : 'ltr'}>
      <header className="kiosk-head">
        <div><b>{t('kiosk_title')}</b><small>{t('kiosk_sub')}</small></div>
        <span className="sp" />
        {rate && <div className="kiosk-rate"><small>{t('kiosk_rate')}</small><b>{num(rate.rate_per_gram, lang)} {rate.currency}/g</b><small>{when(rate.approved_at, lang)}</small></div>}
        <button className="btn ghost" onClick={() => setLang(lang === 'en' ? 'ar' : 'en')}>{lang === 'en' ? 'العربية' : 'English'}</button>
      </header>
      <main className="kiosk-main">
        <section className="kiosk-noor">
          <button className={`noor ${live ? 'live' : ''} ${live && mode === 'speaking' ? 'talking' : ''}`} onClick={() => (live || status === 'connecting' ? end() : start(false))} aria-label={t('kiosk_tap')}>
            <img src={NOOR} alt="Noor, AI-generated portrait" width={220} height={220} />
          </button>
          <div className="noor-state">{status === 'connecting' ? t('voice_connecting') : live ? (mode === 'speaking' ? t('voice_speaking') : t('voice_listening')) : t('kiosk_tap')}</div>
          {live && <button className="btn ghost small" onClick={end}>{t('kiosk_end')}</button>}
          <div className="kiosk-transcript">
            {msgs.slice(-6).map((m, i) => <div key={i} className={`msg ${m.role}`}><div className="bubble" dir="auto">{m.text}</div></div>)}
          </div>
          <form className="chat-input" onSubmit={send}>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t('kiosk_type')} dir="auto" />
            <button className="btn">{t('chat_send')}</button>
          </form>
          {notice && <div className="notice warn">{notice}</div>}
          <p className="small muted">{t('kiosk_privacy')}</p>
        </section>
        <section className="kiosk-shelf">
          {done ? (
            <div className="kiosk-done">
              <h2>{t('kiosk_thanks')}</h2>
              <p>{done.message}</p>
              <p className="small muted">{done.reference} · {done.kind === 'delivery' ? `${t('kiosk_delivery')} · ${done.delivery_date} · ${done.slot}` : t('kiosk_viewing')}</p>
              <button className="btn" onClick={reset}>{t('kiosk_new')}</button>
            </div>
          ) : form ? (
            <form className="kiosk-form" onSubmit={submitForm}>
              <h2>{form.kind === 'delivery' ? t('kiosk_ask_delivery') : t('kiosk_ask_viewing')} · {form.serial}</h2>
              <p className="small">{t('kiosk_request_note')}</p>
              <label className="fld"><span>{t('kiosk_your_name')}</span><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} dir="auto" /></label>
              <label className="fld"><span>{t('kiosk_your_phone')}</span><input required inputMode="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
              {form.kind === 'viewing'
                ? <label className="fld"><span>{t('kiosk_when')}</span><input value={form.preferred_time} onChange={(e) => setForm({ ...form, preferred_time: e.target.value })} dir="auto" /></label>
                : <>
                  <label className="fld"><span>{t('kiosk_address')}</span><textarea required rows={2} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} dir="auto" /></label>
                  <div className="chips">
                    <span className="small muted">{t('kiosk_slot')}:</span>
                    {(['morning', 'afternoon'] as const).map((s) => <button type="button" key={s} className={`chip ${form.slot === s ? 'on' : ''}`} onClick={() => setForm({ ...form, slot: s })}>{t(`kiosk_${s}`)}</button>)}
                  </div>
                </>}
              <div className="actions">
                <button className="btn" disabled={busy}>{t('kiosk_send')}</button>
                <button type="button" className="btn ghost" onClick={() => setForm(null)}>{t('cancel')}</button>
              </div>
            </form>
          ) : focus ? (
            <div className="kiosk-focus">
              <div className="glyph big">{glyph(focus.category)}</div>
              <h2>{focus.design}</h2>
              <div className="kiosk-price">{money(focus.price_incl_vat, cur, lang)}</div>
              <div className="small muted">{focus.serial} · {focus.karat}K · {num(focus.net_weight_g, lang, 3)} g · {t('kiosk_rate')} {focus.rate_per_gram ? `${num(focus.rate_per_gram, lang)} ${cur}/g` : ''}</div>
              <div className="actions">
                <button className="btn" onClick={() => setForm({ kind: 'viewing', serial: focus.serial, name: '', phone: '', preferred_time: '', address: '', slot: 'morning', note: '' })}>{t('kiosk_ask_viewing')}</button>
                <button className="btn ghost" onClick={() => setForm({ kind: 'delivery', serial: focus.serial, name: '', phone: '', preferred_time: '', address: '', slot: 'afternoon', note: '' })}>{t('kiosk_ask_delivery')}</button>
                <button className="btn ghost" onClick={() => setFocus(null)}>{t('kiosk_browse')}</button>
              </div>
              <p className="small muted">{t('kiosk_request_note')}</p>
            </div>
          ) : (
            <>
              <div className="chips">
                <button className={`chip ${!cat ? 'on' : ''}`} onClick={() => setCat('')}>{t('kiosk_all')}</button>
                {CATS.map((c) => <button key={c} className={`chip ${cat === c ? 'on' : ''}`} onClick={() => setCat(c)}>{t(`cat_${c}`)}</button>)}
              </div>
              <div className="kiosk-grid">
                {pieces.map((p) => (
                  <button key={p.serial} className="kiosk-card" onClick={async () => { try { setFocus(await api.kioskPiece(p.serial)); } catch { /* gone */ } }}>
                    <div className="glyph">{glyph(p.category)}</div>
                    <b>{p.design}</b>
                    <div className="small muted">{p.karat}K · {num(p.net_weight_g, lang, 2)} g</div>
                    <div className="kiosk-price">{money(p.price_incl_vat, cur, lang)}</div>
                  </button>
                ))}
                {pieces.length === 0 && <p className="muted">{t('empty')}</p>}
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function glyph(c: string | null) {
  return ({ bangle: '◯', chain: '⌇', necklace: '◡', ring: '◎', earrings: '⫶', bracelet: '⊂', pendant: '◇', set: '❖', coin: '●' } as Record<string, string>)[c ?? ''] ?? '◇';
}
