import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { api, type Consent, type Kyc, type Rate, type User } from '../lib/api';
import { ConsentTag } from './Outreach';
import { KycTag } from './Compliance';
import { stateLabel, tierLabel, useT } from '../lib/i18n';
import { money, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, StateTag, TierTag, useLoad } from '../components/ui';
import { useEffect, useState } from 'react';

export default function ClientDetail() {
  const { id } = useParams();
  const { t, lang } = useT();
  const nav = useNavigate();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const client = useLoad(() => api.client(Number(id)), [id]);
  const cur = user.company.currency;
  const c = client.data;
  const [preparing, setPreparing] = useState(false);
  const prepare = async () => {
    if (!c) return;
    setPreparing(true);
    try { const tray = await api.createTray({ client_id: c.id, build: !c.restricted, limit: 3 }); nav(`/trays/${tray.id}`); }
    finally { setPreparing(false); }
  };
  const [laylaMsg, setLaylaMsg] = useState<string | null>(null);
  const [consent, setConsent] = useState<Consent | null>(null);
  const [source, setSource] = useState('in_store');
  const [consentNote, setConsentNote] = useState('');
  useEffect(() => { if (id) api.consent(Number(id)).then(setConsent).catch(() => setConsent(null)); }, [id]);
  const [kyc, setKyc] = useState<Kyc | null>(null);
  const [doc, setDoc] = useState({ id_type: 'emirates_id', last4: '', expiry: '', note: '' });
  const [scr, setScr] = useState({ status: 'clear', risk_band: 'low', note: '' });
  useEffect(() => { if (id) api.kyc(Number(id)).then(setKyc).catch(() => setKyc(null)); }, [id]);
  const verify = async () => {
    if (!c) return;
    setPreparing(true);
    try { setKyc(await api.kycVerify(c.id, { ...doc, note: doc.note || undefined })); setDoc({ ...doc, last4: '', expiry: '', note: '' }); }
    catch (e) { setLaylaMsg((e as Error).message); }
    finally { setPreparing(false); }
  };
  const screen = async () => {
    if (!c) return;
    setPreparing(true);
    try { setKyc(await api.kycScreening(c.id, { status: scr.status, risk_band: scr.risk_band, note: scr.note || undefined })); }
    catch (e) { setLaylaMsg((e as Error).message); }
    finally { setPreparing(false); }
  };
  const isManager = user.roles.includes('jewellery_manager');
  const record = async (status: 'given' | 'withdrawn') => {
    if (!c) return;
    setPreparing(true);
    try { setConsent(await api.recordConsent(c.id, { status, source, note: consentNote || undefined })); setConsentNote(''); client.reload(); }
    catch (e) { setLaylaMsg((e as Error).message); }
    finally { setPreparing(false); }
  };
  const followup = async () => {
    if (!c) return;
    setPreparing(true);
    try {
      const out = await api.aiLaylaFollowup({ client_id: c.id, channel: c.no_marketing ? 'note' : 'whatsapp' });
      if (out.refused) { setLaylaMsg(`${t('layla_refused')}: ${out.message}`); return; }
      nav(`/agents?draft=${out.draft.id}`);
    } finally { setPreparing(false); }
  };
  return (
    <>
      <TopBar title={c?.name ?? t('loading')} sub={<Link to="/clients">← {t('clients_title')}</Link> } rate={rate}>
        {c && <TierTag tier={c.tier} label={tierLabel(lang, c.tier)} />}
        {c && <button className="btn" disabled={preparing} onClick={prepare}>{preparing ? t('working') : t('prepare_tray')}</button>}
        {c && <button className="btn ghost" disabled={preparing} onClick={followup}>{t('ask_layla_followup')}</button>}
      </TopBar>
      {laylaMsg && <div className="content" style={{ paddingBottom: 0 }}><div className="notice warn">{laylaMsg}</div></div>}
      <div className="content">
        {client.error && <ErrorBox error={client.error} retry={client.reload} />}
        {client.loading && !c && <Loading />}
        {c && (
          <div className="two">
            <div style={{ display: 'grid', gap: 18 }}>
              <Card title={t('recent_orders')}>
                {c.orders.length === 0 ? <Empty /> : (
                  <table className="tbl">
                    <thead><tr><th>{t('number')}</th><th>{t('date')}</th><th>{t('state')}</th><th className="r">{t('amount')}</th></tr></thead>
                    <tbody>{c.orders.map((o) => (
                      <tr key={o.id} className="row" onClick={() => nav(`/documents/${o.id}`)}>
                        <td><b>{o.name}</b></td><td className="num">{when(o.date, lang, false)}</td>
                        <td><StateTag state={o.state} label={stateLabel(lang, o.state)} /></td>
                        <td className="r num">{money(o.amount_total, o.currency, lang)}</td>
                      </tr>))}</tbody>
                  </table>
                )}
              </Card>
              <Card title={t('trays')}>
                {c.trays.length === 0 ? <Empty /> : (
                  <table className="tbl"><tbody>{c.trays.map((tr) => (
                    <tr key={tr.id} className="row" onClick={() => nav(`/trays/${tr.id}`)}>
                      <td><b>{tr.name}</b></td><td>{t(`tray_state_${tr.state}`)}</td><td className="num">{tr.piece_count}</td>
                      <td className="r num">{money(tr.total, cur, lang)}</td></tr>))}</tbody></table>
                )}
              </Card>
              <Card title={t('memos_title')}>
                {c.memos.length === 0 ? <Empty /> : (
                  <table className="tbl"><tbody>{c.memos.map((m) => (
                    <tr key={m.id}><td><b>{m.name}</b></td><td>{m.pieces.map((p) => p.serial).join(', ')}</td>
                      <td className="num">{t('return_by')} {when(m.return_by, lang, false)}</td>
                      <td><StateTag state={m.state} label={stateLabel(lang, m.state)} /></td>
                      <td className="r num">{money(m.insured_value, cur, lang)}</td></tr>))}</tbody></table>
                )}
              </Card>
            </div>
            <Card title={t('clients_sub')}>
              <dl className="dl">
                <dt>{t('tier')}</dt><dd><TierTag tier={c.tier} label={tierLabel(lang, c.tier)} /> {c.restricted && <span className="tag gold">{t('restricted')}</span>}</dd>
                <dt>{t('manager')}</dt><dd>{c.relationship_manager?.name ?? '—'}</dd>
                <dt>{t('deputy')}</dt><dd>{c.deputy?.name ?? '—'}</dd>
                <dt>{t('ai_cap')}</dt><dd>{c.ai_autonomy_cap === 2 ? t('ai_cap_2') : t('ai_cap_3')}</dd>
                <dt>{t('lifetime_value')}</dt><dd className="num">{money(c.lifetime_value, cur, lang)}</dd>
                <dt>{t('preferred_karats')}</dt><dd>{c.preferred_karats ? c.preferred_karats.split(',').map((k) => `${k.trim()}K`).join(' · ') : '—'}</dd>
                <dt>{t('typical_budget')}</dt><dd className="num">{money(c.typical_budget, cur, lang)}</dd>
                <dt>{t('taste')}</dt><dd>{c.taste_notes ?? '—'}</dd>
                <dt>{t('occasions')}</dt><dd>{c.occasions.length ? c.occasions.map((o) => <div key={o.id}>{o.kind} · {when(o.date, lang, false)}</div>) : '—'}</dd>
                <dt>{t('consent')}</dt><dd>
                  {consent ? (
                    <div className="consent">
                      <ConsentTag consent={consent} t={t} />
                      {consent.status !== 'unknown' && <div className="small muted">{consent.source ? t(`source_${consent.source}`) : ''} · {when(consent.date, lang, false)} · {t('consent_recorded_by')} {consent.recorded_by?.name ?? '—'}{consent.note && <> · {consent.note}</>}</div>}
                      <div className="actions small">
                        <select value={source} onChange={(e) => setSource(e.target.value)} aria-label={t('consent_source')}>
                          {['in_store', 'phone', 'form', 'client_message'].map((s) => <option key={s} value={s}>{t(`source_${s}`)}</option>)}
                        </select>
                        <input className="payload" style={{ width: 'auto', flex: 1 }} placeholder={t('send_note_ph')} value={consentNote} onChange={(e) => setConsentNote(e.target.value)} />
                        {consent.status !== 'given' && <button className="btn small" disabled={preparing} onClick={() => record('given')}>{t('consent_record')}</button>}
                        {consent.status !== 'withdrawn' && <button className="btn small ghost" disabled={preparing} onClick={() => record('withdrawn')}>{t('consent_withdraw')}</button>}
                      </div>
                      <div className="small muted">{t('consent_rule')}</div>
                    </div>
                  ) : '—'}
                </dd>
                <dt>{t('no_marketing')}</dt><dd>{c.no_marketing ? '✓' : '—'}</dd>
                <dt>{t('identity')}</dt><dd>
                  {kyc ? (
                    <div className="kyc">
                      <div><KycTag status={kyc.status} t={t} />{kyc.id_type && <span className="small muted"> · {t(`doc_${kyc.id_type}`)} · {kyc.id_last4} · {t('doc_expiry')} {when(kyc.id_expiry, lang, false)} · {t('verified_by')} {kyc.verified_by?.name ?? '—'}</span>}</div>
                      <div className="actions small">
                        <select value={doc.id_type} onChange={(e) => setDoc({ ...doc, id_type: e.target.value })} aria-label={t('doc_type')}>
                          {['emirates_id', 'national_id', 'passport', 'iqama', 'other'].map((k) => <option key={k} value={k}>{t(`doc_${k}`)}</option>)}
                        </select>
                        <input placeholder={t('doc_last4')} maxLength={4} value={doc.last4} onChange={(e) => setDoc({ ...doc, last4: e.target.value })} style={{ width: 72 }} aria-label={t('doc_last4')} />
                        <input type="date" value={doc.expiry} onChange={(e) => setDoc({ ...doc, expiry: e.target.value })} aria-label={t('doc_expiry')} />
                        <button className="btn small" disabled={preparing || doc.last4.length !== 4 || !doc.expiry} onClick={verify}>{t('verify_identity')}</button>
                      </div>
                      <div className="small muted">{t('doc_last4_hint')}</div>
                      <div><span className="muted small">{t('screening')}: </span><span className={`tag ${kyc.screening === 'clear' ? 'ok' : kyc.screening === 'match' ? 'bad' : ''}`}>{t(`scr_${kyc.screening}`)}</span>{kyc.risk_band && <span className="small muted"> · {t('risk_band')} {t(`risk_${kyc.risk_band}`)}</span>}{kyc.screened_by && <span className="small muted"> · {kyc.screened_by.name}</span>}</div>
                      {isManager && (
                        <div className="actions small">
                          <select value={scr.status} onChange={(e) => setScr({ ...scr, status: e.target.value })} aria-label={t('screening')}>
                            {['clear', 'match', 'not_screened'].map((k) => <option key={k} value={k}>{t(`scr_${k}`)}</option>)}
                          </select>
                          <select value={scr.risk_band} onChange={(e) => setScr({ ...scr, risk_band: e.target.value })} aria-label={t('risk_band')}>
                            {['low', 'medium', 'high'].map((k) => <option key={k} value={k}>{t(`risk_${k}`)}</option>)}
                          </select>
                          <input placeholder={t('send_note_ph')} value={scr.note} onChange={(e) => setScr({ ...scr, note: e.target.value })} style={{ flex: 1 }} />
                          <button className="btn small ghost" disabled={preparing} onClick={screen}>{t('record_screening')}</button>
                        </div>
                      )}
                      <div className="small muted">{t('cash_in_window')}: <span className="num">{money(kyc.cash_in_window, cur, lang)}</span> · {t('kyc_rule')}</div>
                    </div>
                  ) : '—'}
                </dd>
                <dt>{t('discreet')}</dt><dd>{c.discreet_billing ? '✓' : '—'}</dd>
                <dt>{t('login')}</dt><dd>{c.email ?? '—'}{c.phone ? ` · ${c.phone}` : ''}</dd>
              </dl>
            </Card>
          </div>
        )}
      </div>
    </>
  );
}
