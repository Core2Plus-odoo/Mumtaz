import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, ApiError, type PublicTray as PT } from '../lib/api';
import { useT } from '../lib/i18n';
import { grams, money, when } from '../lib/format';

/** Plan v3 wireframe 26: the client's phone. No account, the link is the scope,
 *  nothing about her on the page, and a request is not a reservation. */
export default function PublicTray() {
  const { token } = useParams();
  const { t, lang, setLang } = useT();
  const [tray, setTray] = useState<PT | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [asking, setAsking] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [requesting, setRequesting] = useState(false);
  const [preferred, setPreferred] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.publicTray(token!).then(setTray, (e) => setError(e instanceof ApiError ? e : (e as Error)));
  }, [token]);

  const act = async (fn: () => Promise<PT>) => {
    setBusy(true);
    try { setTray(await fn()); } catch (e) { setError(e instanceof ApiError ? e : (e as Error)); } finally { setBusy(false); }
  };

  return (
    <div className="pub">
      <div className="pubhead">
        <span className="mk">J</span>
        <span><b>{t('app')}</b><small>{t('pub_title')}</small></span>
        <span className="sp" />
        <button className="btn ghost small" onClick={() => setLang(lang === 'en' ? 'ar' : 'en')}>{t('language')}</button>
      </div>
      {error && <div className="err" style={{ margin: 16 }}>{error.message || t('pub_expired')}</div>}
      {tray && (
        <div className="pubbody">
          <p className="muted small">{t('pub_sub')}</p>
          {tray.pieces.map((p) => (
            <article key={p.ref} className="card pubpiece">
              <div className="bd">
                <h3>{p.product}</h3>
                <div className="small muted">{p.karat ? `${p.karat}K` : ''} · {grams(p.net_weight_g, lang)}</div>
                <div className="num" style={{ fontSize: '1.3rem', fontWeight: 700, margin: '6px 0' }}>{money(p.price, tray.currency, lang)}</div>
                <div className="small">{p.why.split('\n').map((w, i) => <div key={i}>· {w}</div>)}</div>
                <div className="toolbar" style={{ marginTop: 10 }}>
                  <button className={`btn ${p.feedback === 'like' ? '' : 'ghost'}`} disabled={busy} onClick={() => act(() => api.publicFeedback(token!, p.ref, p.feedback === 'like' ? 'clear' : 'like'))}>♥ {t('pub_like')}</button>
                  <button className={`btn ${p.feedback === 'dislike' ? '' : 'ghost'}`} disabled={busy} onClick={() => act(() => api.publicFeedback(token!, p.ref, p.feedback === 'dislike' ? 'clear' : 'dislike'))}>{t('pub_unlike')}</button>
                  <button className="btn ghost" onClick={() => { setAsking(asking === p.ref ? null : p.ref); setQuestion(p.question ?? ''); }}>{t('pub_ask')}</button>
                </div>
                {p.question && asking !== p.ref && <div className="small" style={{ marginTop: 6, color: 'var(--gold-dark)' }}>{t('asked')}: {p.question}</div>}
                {asking === p.ref && (
                  <div className="toolbar" style={{ marginTop: 8 }}>
                    <input value={question} onChange={(e) => setQuestion(e.target.value)} style={{ flex: 1, minWidth: 0 }} aria-label={t('pub_ask')} />
                    <button className="btn" disabled={busy || !question.trim()} onClick={() => { act(() => api.publicFeedback(token!, p.ref, 'question', question)); setAsking(null); }}>{t('pub_send')}</button>
                  </div>
                )}
              </div>
            </article>
          ))}
          <div className="card"><div className="bd">
            {tray.viewing_requested ? <div className="tag good" style={{ padding: '8px 12px' }}>{t('pub_requested')}</div> : requesting ? (
              <>
                <label className="small">{t('pub_when')}<input value={preferred} onChange={(e) => setPreferred(e.target.value)} style={{ display: 'block', width: '100%', marginTop: 4 }} /></label>
                <label className="small" style={{ display: 'block', marginTop: 8 }}>{t('pub_note')}<input value={note} onChange={(e) => setNote(e.target.value)} style={{ display: 'block', width: '100%', marginTop: 4 }} /></label>
                <button className="btn" style={{ marginTop: 10, width: '100%' }} disabled={busy} onClick={() => act(() => api.publicViewing(token!, preferred, note))}>{t('pub_request')}</button>
              </>
            ) : <button className="btn" style={{ width: '100%' }} onClick={() => setRequesting(true)}>{t('pub_request')}</button>}
            <p className="small muted" style={{ marginTop: 8 }}>{t('pub_request_note')}</p>
            <p className="small muted">{t('pub_expires')} {when(tray.expires, lang)}</p>
          </div></div>
        </div>
      )}
    </div>
  );
}
