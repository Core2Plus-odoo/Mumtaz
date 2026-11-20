// The client's own page, on her phone: sign in by a one-time code a person
// gives her, then today's rate, what she owns (metal value at today's
// approved rate, read from the engine), her selections, her requests and
// her choices. Nothing is bought or paid here; no agent speaks here.
import { useEffect, useState } from 'react';
import { api, ApiError, type ClientHome, type PublicTray as PT } from '../lib/api';
import { useT } from '../lib/i18n';
import { grams, money, num, when } from '../lib/format';

const KEY = 'jawhar_client_token';
function readToken() { try { return localStorage.getItem(KEY) || ''; } catch { return ''; } }
function saveToken(t: string) { try { if (t) localStorage.setItem(KEY, t); else localStorage.removeItem(KEY); } catch { /* fine */ } }

/** A piece photo fetched with her token (an <img> cannot send a header), shown from a blob; nothing in the URL. */
function OwnedImage({ url, token }: { url: string; token: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let alive = true; let obj: string | null = null;
    fetch(url, { headers: { 'X-Client-Token': token } }).then((r) => (r.ok ? r.blob() : Promise.reject(r.status)))
      .then((b) => { obj = URL.createObjectURL(b); if (alive) setSrc(obj); }).catch(() => { if (alive) setSrc(null); });
    return () => { alive = false; if (obj) URL.revokeObjectURL(obj); };
  }, [url, token]);
  return src ? <img src={src} alt="" /> : <span style={{ width: 72, height: 72, borderRadius: 10, background: 'var(--paper2)', display: 'inline-block' }} />;
}

export default function ClientApp() {
  const { t, lang, setLang } = useT();
  const [token, setToken] = useState(readToken);
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState<{ message: string; code?: string } | null>(null);
  const [home, setHome] = useState<ClientHome | null>(null);
  const [tray, setTray] = useState<PT | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = (tk: string) => api.clientHome(tk).then(setHome, (e) => { if (e instanceof ApiError && e.status === 401) { saveToken(''); setToken(''); } else setError((e as Error).message); });
  useEffect(() => { if (token) load(token); }, [token]);
  const run = async (fn: () => Promise<void>) => { setBusy(true); setError(null); try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); } };
  const getCode = () => run(async () => { const out = await api.clientCode(phone, lang); setSent({ message: t('me_code_sent'), code: out.code }); });
  const signIn = () => run(async () => { const out = await api.clientVerify(phone, code); saveToken(out.token); setToken(out.token); setCode(''); setSent(null); });
  const signOut = () => run(async () => { await api.clientSignout(token); saveToken(''); setToken(''); setHome(null); setTray(null); });
  const consent = (status: 'given' | 'withdrawn') => run(async () => { const me = await api.clientConsent(token, status); setHome((h) => (h ? { ...h, me } : h)); });
  const kstate = (s: string) => (t(`kstate_${s}`) === `kstate_${s}` ? s : t(`kstate_${s}`));
  return (
    <div className="pub">
      <div className="pubhead">
        <span className="mk">J</span>
        <span><b>{t('app')}</b><small>{t('me_title')}</small></span>
        <span className="sp" />
        <button className="btn ghost small" onClick={() => setLang(lang === 'en' ? 'ar' : 'en')}>{t('language')}</button>
        {token && <button className="btn ghost small" onClick={signOut}>{t('me_sign_out')}</button>}
      </div>
      {error && <div className="err" style={{ margin: 16 }}>{error}</div>}
      {!token ? (
        <div className="pubbody">
          <p className="muted small">{t('me_sub')}</p>
          <div className="card"><div className="bd me-form">
            <label className="small muted">{t('me_phone')}<input inputMode="tel" placeholder="+971 50 …" value={phone} onChange={(e) => setPhone(e.target.value)} aria-label={t('me_phone')} /></label>
            <div className="small muted">{t('me_phone_hint')}</div>
            {!sent ? (
              <button className="btn" disabled={busy || phone.replace(/\D/g, '').length < 7} onClick={getCode}>{t('me_get_code')}</button>
            ) : (
              <>
                <div className="notice ok">{sent.message}{sent.code && <> <b>{t('me_demo_code')} {sent.code}</b></>}</div>
                <label className="small muted">{t('me_code')}<input inputMode="numeric" maxLength={6} placeholder="••••••" value={code} onChange={(e) => setCode(e.target.value)} aria-label={t('me_code')} /></label>
                <button className="btn" disabled={busy || code.length !== 6} onClick={signIn}>{t('me_sign_in')}</button>
              </>
            )}
            <p className="small muted">{t('me_no_payment')}</p>
          </div></div>
        </div>
      ) : !home ? <div className="pubbody"><p className="muted">…</p></div> : tray ? (
        <div className="pubbody">
          <button className="btn ghost small" onClick={() => setTray(null)}>← {t('me_trays')}</button>
          <p className="muted small">{t('pub_sub')}</p>
          {tray.pieces.map((p) => (
            <article key={p.ref} className="card pubpiece"><div className="bd">
              <h3>{p.product}</h3>
              <div className="small muted">{p.karat ? `${p.karat}K` : ''} · {grams(p.net_weight_g, lang)}</div>
              <div className="num" style={{ fontSize: '1.3rem', fontWeight: 700, margin: '6px 0' }}>{money(p.price, tray.currency, lang)}</div>
            </div></article>
          ))}
        </div>
      ) : (
        <div className="pubbody">
          <h2 style={{ margin: 0 }}>{t('me_welcome')}, {home.me.first_name}</h2>
          {home.me.advisor && <div className="small muted">{t('me_advisor')}: {home.me.advisor}</div>}
          <div className="card"><div className="bd">
            <div className="small muted">{t('me_rate_today')}</div>
            {home.rate ? <div className="me-big num">{num(home.rate.rate_per_gram, lang, 2)} {home.rate.currency}/g</div> : <div className="muted">—</div>}
          </div></div>
          <div className="card"><div className="bd">
            <h3 style={{ margin: '0 0 4px' }}>{t('me_owned')}</h3>
            <div className="small muted">{t('me_owned_sub')}</div>
            {home.owned.length === 0 ? <p className="muted">{t('me_nothing_yet')}</p> : (
              <>
                {home.metal_value_today != null && <div className="num" style={{ margin: '8px 0', fontWeight: 700 }}>{num(home.fine_g, lang, 1)} {t('fine_g')} · {money(home.metal_value_today, home.rate?.currency ?? '', lang)} {t('me_metal_today')}</div>}
                {home.owned.map((p) => (
                  <div key={p.serial} className="me-piece" style={{ padding: '8px 0', borderTop: '1px solid var(--paper3)' }}>
                    {p.image_url ? <OwnedImage url={p.image_url} token={token} /> : <span style={{ width: 72, height: 72, borderRadius: 10, background: 'var(--paper2)', display: 'inline-block' }} />}
                    <div>
                      <b>{p.design}</b><div className="small muted">{p.karat}K · {grams(p.net_weight_g, lang)} · {p.serial}</div>
                      <div className="small">{t('me_bought')} {when(p.bought_on, lang, false)}{p.invoice && ` · ${p.invoice}`}{p.metal_value_today != null && <> · <span className="num">{money(p.metal_value_today, home.rate?.currency ?? '', lang)}</span> {t('me_metal_today')}</>}</div>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div></div>
          <div className="card"><div className="bd">
            <h3 style={{ margin: '0 0 6px' }}>{t('me_trays')}</h3>
            {home.trays.length === 0 ? <p className="muted">{t('me_nothing_yet')}</p> : home.trays.map((tr) => (
              <div key={tr.id} className="ln" style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
                <span>{tr.name} · {tr.pieces} {t('pieces_word')} · {t(`tray_state_${tr.state}`)}</span>
                <button className="btn small ghost" disabled={busy} onClick={() => run(async () => setTray(await api.clientTray(token, tr.id)))}>{t('me_open')}</button>
              </div>
            ))}
          </div></div>
          <div className="card"><div className="bd">
            <h3 style={{ margin: '0 0 6px' }}>{t('me_requests')}</h3>
            {home.requests.length === 0 ? <p className="muted">{t('me_nothing_yet')}</p> : home.requests.map((r) => (
              <div key={r.id} className="small" style={{ padding: '4px 0' }}>{r.name} · {r.design} · {kstate(r.state)} · {when(r.at, lang, false)}</div>
            ))}
          </div></div>
          <div className="card"><div className="bd">
            <h3 style={{ margin: '0 0 6px' }}>{t('me_choices')}</h3>
            <p className="small">{home.me.consent.may_message ? t('me_consent_on') : t('me_consent_off')}</p>
            {home.me.consent.may_message
              ? <button className="btn ghost small" disabled={busy} onClick={() => consent('withdrawn')}>{t('me_withdraw')}</button>
              : <button className="btn small" disabled={busy} onClick={() => consent('given')}>{t('me_allow')}</button>}
          </div></div>
          <p className="small muted">{t('me_no_payment')}</p>
        </div>
      )}
    </div>
  );
}
