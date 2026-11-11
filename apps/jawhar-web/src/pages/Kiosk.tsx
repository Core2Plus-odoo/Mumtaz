// The Virtual Sales Officer: a kiosk for clients, in store or on the web,
// in the owner's concept: portrait, teal and gold, Noor greeting with a
// speech bubble, product photos on the cards. No sign-in. Noor (an
// ElevenLabs conversational agent) talks and listens; every price she
// states comes from the public shelf endpoints, which carry no internal ids
// and no client data. The only write is a request, and a request is not a
// reservation: a person confirms.
import { useEffect, useRef, useState } from 'react';
import type { Conversation as Convo, Mode, Status } from '@elevenlabs/client';
import { api, type KioskPiece, type KioskRequestOut } from '../lib/api';
import { useT } from '../lib/i18n';
import { money, num, when } from '../lib/format';
import TryOn from '../components/TryOn';
import { usesFace, usesHand, type Category } from '../lib/tryon';

const AVATAR = '/app/agents/noor-avatar.webp';
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
  const [tryon, setTryon] = useState<KioskPiece | null>(null);
  const convo = useRef<Convo | null>(null);
  const cur = rate?.currency ?? 'AED';

  const load = async (category = cat) => {
    const r = await api.kioskPieces({ category: category || undefined, limit: 8 });
    setPieces(r.items);
  };
  useEffect(() => {
    api.kioskRate().then((r) => setRate(r.rate)).catch(() => setRate(null));
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
      setPieces(r.items); setFocus(null); setForm(null); if (category) setCat(category);
      if (!r.items.length) return 'Nothing on the shelf matches.';
      return r.items.map((p) => `${p.serial}: ${p.design}, ${p.karat}K, ${p.net_weight_g} g net, ${p.price_incl_vat} ${p.currency} incl. VAT`).join('; ');
    },
    kiosk_show_piece: async ({ serial }: { serial: string }) => {
      try { setFocus(await api.kioskPiece(serial)); setForm(null); } catch { /* not on the shelf */ }
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
    try { const out = await api.kioskRequest({ ...form, lang, channel: 'store' }); setDone(out); setForm(null); }
    catch (ex) { setNotice((ex as Error).message); } finally { setBusy(false); }
  };
  const reset = async () => { await end(); setMsgs([]); setDone(null); setForm(null); setFocus(null); setCat(''); void load(''); };
  const live = status === 'connected';
  const lastAgent = [...msgs].reverse().find((m) => m.role === 'agent')?.text;
  const bubble = status === 'connecting' ? t('voice_connecting') : lastAgent ?? t('kiosk_greeting');
  const openForm = (kind: Form['kind'], serial: string) => setForm({ kind, serial, name: '', phone: '', preferred_time: '', address: '', slot: kind === 'delivery' ? 'afternoon' : 'morning', note: '' });

  return (
    <div className={`kiosk2 ${lang === 'ar' ? 'rtl' : ''}`} dir={lang === 'ar' ? 'rtl' : 'ltr'}>
      <header className="k2-head">
        <div className="k2-brand"><span className="k2-mark">J</span><div><b>{t('kiosk_title')}</b><small>{t('kiosk_sub')}</small></div></div>
        <span className="sp" />
        {rate && <div className="k2-rate"><small>{t('kiosk_rate')}</small><b>{num(rate.rate_per_gram, lang)} {rate.currency}/g</b><small>{when(rate.approved_at, lang, false)}</small></div>}
        <button className="k2-lang" onClick={() => setLang(lang === 'en' ? 'ar' : 'en')}>{lang === 'en' ? 'العربية' : 'English'}</button>
      </header>

      <section className="k2-noor">
        <div className="k2-stage">
          <span className="k2-spark s1">✦</span><span className="k2-spark s2">✦</span><span className="k2-spark s3">✧</span>
          <button className={`k2-avatar ${live ? 'live' : ''} ${live && mode === 'speaking' ? 'talking' : ''}`} onClick={() => (live || status === 'connecting' ? end() : start(false))} aria-label={t('kiosk_tap')}>
            <img src={AVATAR} alt="Noor, AI-generated illustration" width={260} height={260} />
          </button>
          <span className="k2-badge mic" aria-hidden="true">{live ? '●' : '🎤'}</span>
        </div>
        <div className="k2-bubble" dir="auto">
          <b>{live ? (mode === 'speaking' ? t('voice_speaking') : t('voice_listening')) : `${t('kiosk_hello')}`}</b>
          <p>{bubble}</p>
          {msgs.length > 0 && msgs[msgs.length - 1].role === 'user' && <small className="muted">“{msgs[msgs.length - 1].text}”</small>}
        </div>
        <div className="k2-talk">
          <button className={`k2-btn ${live ? 'stop' : ''}`} onClick={() => (live || status === 'connecting' ? end() : start(false))}>{live ? t('kiosk_end') : t('kiosk_tap')}</button>
          <form className="k2-type" onSubmit={send}>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t('kiosk_type')} dir="auto" />
            <button className="k2-send" aria-label={t('chat_send')}>➤</button>
          </form>
        </div>
        {notice && <div className="notice warn">{notice}</div>}
      </section>

      <section className="k2-shelf">
        {done ? (
          <div className="k2-panel">
            <h2>{t('kiosk_thanks')}</h2>
            <p>{done.message}</p>
            <p className="small muted">{done.reference} · {done.kind === 'delivery' ? `${t('kiosk_delivery')} · ${done.delivery_date} · ${done.slot}` : t('kiosk_viewing')}</p>
            <button className="k2-btn" onClick={reset}>{t('kiosk_new')}</button>
          </div>
        ) : form ? (
          <form className="k2-panel" onSubmit={submitForm}>
            <h2>{form.kind === 'delivery' ? t('kiosk_ask_delivery') : t('kiosk_ask_viewing')}</h2>
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
              <button className="k2-btn" disabled={busy}>{t('kiosk_send')}</button>
              <button type="button" className="k2-btn ghost" onClick={() => setForm(null)}>{t('cancel')}</button>
            </div>
          </form>
        ) : focus ? (
          <div className="k2-panel k2-focus">
            <div className="k2-photo big">{focus.image_url ? <img src={focus.image_url} alt={focus.design} /> : <span className="glyph">{glyph(focus.category)}</span>}</div>
            <div>
              <h2>{focus.design}</h2>
              <div className="k2-price">{money(focus.price_incl_vat, cur, lang)}</div>
              <div className="small muted">{focus.serial} · {focus.karat}K · {num(focus.net_weight_g, lang, 3)} g{focus.rate_per_gram ? ` · ${t('kiosk_rate')} ${num(focus.rate_per_gram, lang)} ${cur}/g` : ''}</div>
              <div className="actions">
                {focus.tryon_url && (usesFace(focus.category) || usesHand(focus.category)) && (
                  <button className="k2-btn tryon-btn" onClick={() => setTryon(focus)}>📷 {t('tryon_button')}</button>
                )}
                <button className="k2-btn" onClick={() => openForm('viewing', focus.serial)}>{t('kiosk_ask_viewing')}</button>
                <button className="k2-btn gold" onClick={() => openForm('delivery', focus.serial)}>{t('kiosk_ask_delivery')}</button>
                <button className="k2-btn ghost" onClick={() => setFocus(null)}>{t('kiosk_browse')}</button>
              </div>
              <p className="small muted">{t('kiosk_request_note')}</p>
            </div>
          </div>
        ) : (
          <>
            <div className="chips k2-chips">
              <button className={`chip ${!cat ? 'on' : ''}`} onClick={() => setCat('')}>{t('kiosk_all')}</button>
              {CATS.map((c) => <button key={c} className={`chip ${cat === c ? 'on' : ''}`} onClick={() => setCat(c)}>{t(`cat_${c}`)}</button>)}
            </div>
            <div className="k2-grid">
              {pieces.map((p) => (
                <button key={p.serial} className="k2-card" onClick={async () => { try { setFocus(await api.kioskPiece(p.serial)); } catch { /* gone */ } }}>
                  <b>{p.karat}K {t(`cat_${p.category ?? 'pendant'}`)}</b>
                  <div className="k2-photo">{p.image_url ? <img src={p.image_url} alt={p.design} loading="lazy" /> : <span className="glyph">{glyph(p.category)}</span>}</div>
                  <div className="k2-cardfoot"><span className="small">{num(p.net_weight_g, lang, 2)} g</span><span className="k2-price">{money(p.price_incl_vat, cur, lang)}</span></div>
                </button>
              ))}
              {pieces.length === 0 && <p className="muted">{t('empty')}</p>}
            </div>
          </>
        )}
        <p className="k2-privacy">{t('kiosk_privacy')}</p>
      </section>
      {tryon && tryon.tryon_url && (
        <TryOn category={tryon.category as Category} cutoutUrl={tryon.tryon_url} label={tryon.design}
          onClose={() => setTryon(null)} onAskViewing={() => { setTryon(null); openForm('viewing', tryon.serial); }} />
      )}
    </div>
  );
}

function glyph(c: string | null) {
  return ({ bangle: '◯', chain: '⌇', necklace: '◡', ring: '◎', earrings: '⫶', bracelet: '⊂', pendant: '◇', set: '❖', coin: '●' } as Record<string, string>)[c ?? ''] ?? '◇';
}
