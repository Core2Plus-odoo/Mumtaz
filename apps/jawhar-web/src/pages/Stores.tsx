// Stores and transfers: what each store holds in pieces, fine grams and
// value; transfers on the road (dispatch, receive, report lost); and
// today's gold count per store in fine grams, scanned by serial, closed by
// a manager with a note.
import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { api, type Rate, type Reconciliation, type StoreSummary, type Transfer, type User } from '../lib/api';
import { useT } from '../lib/i18n';
import { money, num, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, useLoad } from '../components/ui';

export default function Stores() {
  const { t, lang } = useT();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const stores = useLoad(() => api.stores());
  const transfers = useLoad(() => api.transfers('all'));
  const [storeId, setStoreId] = useState<number | null>(null);
  const [rec, setRec] = useState<Reconciliation | null>(null);
  const [scan, setScan] = useState('');
  const [closeNote, setCloseNote] = useState('');
  const [form, setForm] = useState({ from_id: 0, to_id: 0, serials: '', note: '' });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'warn'; text: string } | null>(null);
  const isManager = user.roles.includes('jewellery_manager');
  const items = stores.data?.items ?? [];
  useEffect(() => {
    if (!storeId && items.length) setStoreId(stores.data?.my_store?.id ?? items[0].id);
    if (items.length >= 2 && !form.from_id) setForm((f) => ({ ...f, from_id: items[0].id, to_id: items[1].id }));
  }, [items.length]);
  const current = items.find((s) => s.id === storeId) ?? null;
  useEffect(() => {
    if (!current) { setRec(null); return; }
    if (current.today) api.reconciliation(current.today.id).then(setRec).catch(() => setRec(null)); else setRec(null);
  }, [current?.id, current?.today?.id]);
  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    setBusy(true); setMsg(null);
    try { await fn(); if (ok) setMsg({ kind: 'ok', text: ok }); stores.reload(); transfers.reload(); }
    catch (e) { setMsg({ kind: 'warn', text: (e as Error).message }); }
    finally { setBusy(false); }
  };
  const serialsOf = (text: string) => text.split(/[\n,;\s]+/).map((s) => s.trim()).filter(Boolean);
  const tstate = (s: string) => t(`tstate_${s}`);
  const pct = (s: StoreSummary) => (s.limit_fine_g ? Math.min(100, Math.round((s.fine_g / s.limit_fine_g) * 100)) : 0);
  return (
    <>
      <TopBar title={t('stores_title')} sub={t('stores_sub')} rate={rate} />
      <div className="content">
        {msg && <div className={`notice ${msg.kind}`}>{msg.text}</div>}
        {stores.error && <ErrorBox error={stores.error} retry={stores.reload} />}
        {stores.loading && !stores.data ? <Loading /> : (
          <div className="storegrid">
            {items.map((s) => (
              <div key={s.id} className={`storecard ${s.id === storeId ? 'on' : ''}`} onClick={() => setStoreId(s.id)} role="button" tabIndex={0}>
                <h4>{s.name} <span className="muted small">{s.code}</span>{s.over_limit && <span className="tag bad" style={{ marginInlineStart: 6 }}>{t('over_limit')}</span>}</h4>
                <div><b className="num">{s.pieces}</b> {t('pieces_word')} · <b className="num">{num(s.fine_g, lang, 1)}</b> {t('fine_g')}{s.value != null && <> · <span className="num">{money(s.value, s.currency, lang)}</span></>}</div>
                {s.limit_fine_g && <><div className="bar"><i className={s.over_limit ? 'over' : ''} style={{ width: `${pct(s)}%` }} /></div><div className="small muted">{t('store_limit')} {num(s.limit_fine_g, lang, 0)} {t('fine_g')}</div></>}
                <div className="small muted">{t('on_the_road_out')}: {s.in_transit_out.pieces} · {t('on_the_road_in')}: {s.in_transit_in.pieces}</div>
                <div className="small">{s.today ? <>{t('todays_count')}: {s.today.name} · {t(`rstate_${s.today.state}`)}{s.today.missing_count > 0 && <span className="tag bad" style={{ marginInlineStart: 6 }}>{s.today.missing_count} {t('missing').toLowerCase()}</span>}</> : <span className="muted">{t('no_count_yet')}</span>}</div>
              </div>
            ))}
          </div>
        )}
        <div className="two" style={{ marginTop: 18 }}>
          <div style={{ display: 'grid', gap: 18 }}>
            <Card title={t('transfers')}>
              {transfers.error && <ErrorBox error={transfers.error} retry={transfers.reload} />}
              {transfers.loading && !transfers.data ? <Loading /> : transfers.data && (
                transfers.data.items.length === 0 ? <Empty /> : (
                  <table className="tbl">
                    <thead><tr><th>{t('number')}</th><th>{t('from_store')}</th><th>{t('to_store')}</th><th className="r">{t('pieces_word')}</th><th className="r">{t('fine_g')}</th><th>{t('state')}</th><th></th></tr></thead>
                    <tbody>{transfers.data.items.map((tr: Transfer) => (
                      <tr key={tr.id}>
                        <td><b>{tr.name}</b><div className="small muted">{tr.pieces.map((p) => p.serial).join(', ')}</div></td>
                        <td>{tr.from.name}</td><td>{tr.to.name}</td>
                        <td className="r num">{tr.piece_count}</td><td className="r num">{num(tr.fine_g, lang, 2)}</td>
                        <td><span className={`tag ${tr.state === 'lost' ? 'bad' : tr.overdue ? 'warn' : tr.state === 'received' ? 'ok' : ''}`}>{tstate(tr.state)}{tr.overdue && ` · ${t('overdue')}`}</span>
                          <div className="small muted">{tr.dispatched_at ? `${tr.dispatched_by?.name} · ${when(tr.dispatched_at, lang)}` : ''}{tr.received_at ? ` → ${tr.received_by?.name} · ${when(tr.received_at, lang)}` : ''}</div></td>
                        <td className="r">
                          {tr.state === 'draft' && <button className="btn small" disabled={busy} onClick={() => run(() => api.transferAct(tr.id, 'dispatch'))}>{t('dispatch')}</button>}
                          {tr.state === 'in_transit' && <button className="btn small" disabled={busy} onClick={() => run(() => api.transferAct(tr.id, 'receive'))}>{t('receive')}</button>}
                          {tr.state === 'in_transit' && isManager && <button className="btn small ghost" disabled={busy} onClick={() => run(() => api.transferAct(tr.id, 'lost', 'Reported from the Stores screen'))}>{t('report_lost')}</button>}
                        </td>
                      </tr>))}</tbody>
                  </table>
                )
              )}
              <div className="kyc" style={{ marginTop: 12 }}>
                <b>{t('new_transfer')}</b>
                <div className="actions">
                  <select value={form.from_id} onChange={(e) => setForm({ ...form, from_id: Number(e.target.value) })} aria-label={t('from_store')}>{items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
                  <span>→</span>
                  <select value={form.to_id} onChange={(e) => setForm({ ...form, to_id: Number(e.target.value) })} aria-label={t('to_store')}>{items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
                </div>
                <textarea className="payload" rows={2} placeholder={t('serials_ph')} value={form.serials} onChange={(e) => setForm({ ...form, serials: e.target.value })} />
                <div className="actions">
                  <input className="payload" style={{ flex: 1, width: 'auto' }} placeholder={t('note')} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
                  <button className="btn" disabled={busy || !form.serials.trim() || form.from_id === form.to_id} onClick={() => run(() => api.createTransfer({ from_id: form.from_id, to_id: form.to_id, serials: serialsOf(form.serials), note: form.note || undefined, dispatch: true }).then(() => setForm({ ...form, serials: '', note: '' })), t('saved'))}>{t('create_and_dispatch')}</button>
                </div>
              </div>
            </Card>
          </div>
          <Card title={`${t('reconciliation')}${current ? ` · ${current.name}` : ''}`} sub={rec ? `${rec.name} · ${when(rec.date, lang, false)} · ${t(`rstate_${rec.state}`)}` : undefined}>
            <p className="small muted">{t('count_rule')}</p>
            {!current ? <Empty /> : !rec ? (
              <button className="btn" disabled={busy} onClick={() => run(() => api.openReconciliation(current.id).then(setRec))}>{t('start_count')}</button>
            ) : (
              <div className="kyc">
                <div className="bk">
                  <div className="ln"><span>{t('expected')}</span><span className="num">{rec.expected_count} {t('pieces_word')} · {num(rec.expected_fine_g, lang, 3)} {t('fine_g')}</span></div>
                  <div className="ln"><span>{t('counted')}</span><span className="num">{rec.counted_count} {t('pieces_word')} · {num(rec.counted_fine_g, lang, 3)} {t('fine_g')}</span></div>
                  <div className="ln total"><span>{t('variance')}</span><span className={`num ${rec.variance_fine_g ? 'bad' : ''}`}>{rec.variance_fine_g > 0 ? '+' : ''}{num(rec.variance_fine_g, lang, 3)} {t('fine_g')} · {rec.missing_count} {t('missing').toLowerCase()}</span></div>
                </div>
                {rec.missing && rec.missing.length > 0 && <div><div className="small muted">{t('missing')}</div><div className="chips">{rec.missing.map((s) => <span key={s} className="miss">{s}</span>)}</div></div>}
                {rec.extra_serials.length > 0 && <div><div className="small muted">{t('extras')}</div><div className="chips">{rec.extra_serials.map((s) => <span key={s}>{s}</span>)}</div></div>}
                {rec.state === 'open' && (
                  <>
                    <textarea className="payload" rows={2} placeholder={t('scan_serials')} value={scan} onChange={(e) => setScan(e.target.value)} />
                    <div className="actions">
                      <button className="btn" disabled={busy || !scan.trim()} onClick={() => run(() => api.reconciliationCount(rec.id, serialsOf(scan)).then((r) => { setRec(r); setScan(''); }))}>{t('add_to_count')}</button>
                      {isManager && <>
                        <input className="payload" style={{ flex: 1, width: 'auto' }} placeholder={t('close_note_ph')} value={closeNote} onChange={(e) => setCloseNote(e.target.value)} />
                        <button className="btn ghost" disabled={busy} onClick={() => run(() => api.reconciliationClose(rec.id, closeNote || undefined).then(setRec), t('saved'))}>{t('close_count')}</button>
                      </>}
                    </div>
                  </>
                )}
                {rec.state === 'closed' && <div className="notice ok">{t('rstate_closed')} · {rec.closed_by} · {when(rec.closed_at, lang)}{rec.note && <> · {rec.note}</>}</div>}
                {rec.lines && <div className="small muted">{rec.lines.length} {t('pieces_word')} · <Link to={`/pieces?store=${current.id}`}>{t('nav_pieces')} →</Link></div>}
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
