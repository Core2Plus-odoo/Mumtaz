import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import {
  api, ApiError, type ClientDetail, type CounterPiece, type CounterResult, type OldGold, type PaymentMethod,
  type Rate, type Readiness, type User,
} from '../lib/api';
import { tierLabel, useT } from '../lib/i18n';
import { grams, money, num, pct, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, StateTag, TierTag, useLoad } from '../components/ui';
import { stateLabel } from '../lib/i18n';

const KARATS = ['24', '22', '21', '18', '14', '9'];

/** Plan v3 §27: AI explains and prepares; pricing, stock, payment and
 *  accounting rules decide whether the sale can proceed. Every figure here is
 *  the server's; the commit is one call and one transaction. */
export default function Counter() {
  const { t, lang } = useT();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const cur = user.company.currency;

  const [query, setQuery] = useState('');
  const [piece, setPiece] = useState<CounterPiece | null>(null);
  const [pieceError, setPieceError] = useState<Error | null>(null);
  const [discount, setDiscount] = useState(0);
  const [clientQ, setClientQ] = useState('');
  const [client, setClient] = useState<ClientDetail | null>(null);
  const [oldGold, setOldGold] = useState<OldGold | null>(null);
  const [ogForm, setOgForm] = useState({ weight: '', karat: '21', melt: '2', buyback: '0' });
  const [ogBusy, setOgBusy] = useState(false);
  const [ogError, setOgError] = useState<Error | null>(null);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [journal, setJournal] = useState<number | ''>('');
  const [amount, setAmount] = useState('');
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [commitError, setCommitError] = useState<Error | null>(null);
  const [result, setResult] = useState<CounterResult | null>(null);

  const clients = useLoad(() => api.clients({ q: clientQ, limit: 6 }), [clientQ]);
  const intakes = useLoad(() => (client ? api.oldGold({ client_id: client.id, unused: true, limit: 10 }) : Promise.resolve({ items: [] })), [client?.id, oldGold?.id]);

  useEffect(() => { api.paymentMethods().then((r) => { setMethods(r.items); if (r.items[0]) setJournal(r.items[0].id); }, () => {}); }, []);

  // readiness follows every choice
  useEffect(() => {
    if (!piece && !client) { setReadiness(null); return; }
    let alive = true;
    api.counterReadiness({ piece_id: piece?.id, client_id: client?.id, discount, old_gold_id: oldGold?.id })
      .then((r) => alive && setReadiness(r), () => alive && setReadiness(null));
    return () => { alive = false; };
  }, [piece?.id, client?.id, discount, oldGold?.id]);

  const lookup = async (q = query, d = discount) => {
    if (!q.trim()) return;
    setPieceError(null);
    try { setPiece(await api.counterPiece(q.trim(), d || undefined)); }
    catch (e) { setPiece(null); setPieceError(e instanceof ApiError ? e : (e as Error)); }
  };
  const changeDiscount = (d: number) => { setDiscount(d); if (piece) lookup(piece.serial, d); };

  const createIntake = async () => {
    setOgBusy(true); setOgError(null);
    try {
      const og = await api.createOldGold({ client_id: client?.id, gross_weight_g: Number(ogForm.weight), karat: ogForm.karat,
        melt_loss_pct: Number(ogForm.melt), buyback_discount_pct: Number(ogForm.buyback) });
      setOldGold(og); setOgForm({ ...ogForm, weight: '' });
    } catch (e) { setOgError(e instanceof ApiError ? e : (e as Error)); }
    finally { setOgBusy(false); }
  };
  const approveIntake = async () => {
    if (!oldGold) return;
    setOgBusy(true); setOgError(null);
    try { setOldGold(await api.approveOldGold(oldGold.id)); }
    catch (e) { setOgError(e instanceof ApiError ? e : (e as Error)); }
    finally { setOgBusy(false); }
  };

  const pieces_total = piece?.breakdown?.total ?? 0;
  const credit = oldGold && oldGold.state === 'confirmed' ? oldGold.value : 0;
  const due = Math.max(0, pieces_total - credit);

  const commit = async () => {
    if (!piece || !client) return;
    setReviewing(false); setCommitting(true); setCommitError(null);
    try {
      const out = await api.counterCommit({ client_id: client.id, piece_id: piece.id, discount: discount || undefined,
        journal_id: journal || undefined, amount: amount ? Number(amount) : undefined, old_gold_id: oldGold?.id });
      setResult(out);
    } catch (e) { setCommitError(e instanceof ApiError ? e : (e as Error)); }
    finally { setCommitting(false); }
  };
  const reset = () => { setPiece(null); setQuery(''); setDiscount(0); setClient(null); setOldGold(null); setAmount(''); setResult(null); setReadiness(null); };

  const status = piece?.availability.status;
  const statusTone = status === 'on_shelf' ? 'good' : status === 'sold' ? 'bad' : 'warn';

  if (result) {
    const o = result.order; const inv = result.invoice;
    const paid = result.payments.reduce((s, p) => s + p.amount, 0);
    return (
      <>
        <TopBar title={t('receipt')} sub={t('counter_sub')} rate={rate}>
          <button className="btn ghost" onClick={() => window.print()}>{t('print')}</button>
          <button className="btn" onClick={reset}>{t('new_sale')}</button>
        </TopBar>
        <div className="content">
          <div className="tag good" role="status" style={{ justifySelf: 'start', padding: '8px 12px' }}>{t('committed')}</div>
          <Card title={`${inv.name} · ${o.name}`} sub={`${o.client?.name ?? ''} · ${when(inv.date, lang, false)} · ${t('served_by')} ${o.salesperson?.name ?? user.name}`}>
            <table className="tbl receipt">
              <thead><tr><th>{t('product')}</th><th>{t('serial')}</th><th className="r">{t('subtotal')}</th><th className="r">{t('total')}</th></tr></thead>
              <tbody>{(inv.lines ?? []).map((l) => (
                <tr key={l.id}>
                  <td>{l.description}{l.snapshot && (
                    <div className="small muted">{t('rate_per_gram')} {num(l.snapshot.rate_per_gram, lang)}/{t('unit_g')} · {t('fine_weight')} {grams(l.snapshot.fine_weight_g, lang)} · {t('metal_value')} {money(l.snapshot.metal_value, inv.currency, lang)} · {t('wastage_value')} {money(l.snapshot.wastage_value, inv.currency, lang)} · {t('making_charge')} {money(l.snapshot.making_charge, inv.currency, lang)} · {t('stones_value')} {money(l.snapshot.stones_value, inv.currency, lang)}</div>
                  )}</td>
                  <td>{l.piece?.serial ?? '—'}</td>
                  <td className="r num">{money(l.subtotal, inv.currency, lang)}</td>
                  <td className="r num"><b>{money(l.total, inv.currency, lang)}</b></td>
                </tr>))}</tbody>
            </table>
            <div className="bk" style={{ maxWidth: 420, marginInlineStart: 'auto', marginTop: 12 }}>
              <div className="ln"><span>{t('vat')}</span><span className="num">{money(inv.amount_tax, inv.currency, lang)}</span></div>
              <div className="ln total"><span>{t('total')}</span><span className="num">{money(inv.amount_total, inv.currency, lang)}</span></div>
              <div className="ln"><span>{t('paid_now')} · {result.payments.map((p) => p.journal?.name).join(', ')}</span><span className="num">{money(paid, inv.currency, lang)}</span></div>
              <div className="ln"><span>{t('outstanding')}</span><span className="num">{money(inv.amount_residual, inv.currency, lang)}</span></div>
              <div className="ln"><span>{t('delivery')}</span><span>{result.deliveries.map((d) => `${d.name} · ${stateLabel(lang, d.state === 'done' ? 'confirmed' : d.state)}`).join(', ')}</span></div>
            </div>
            <p className="small muted">
              <Link to={`/documents/${o.id}`}>{o.name}</Link> · <Link to={`/invoices/${inv.id}`}>{inv.name}</Link>
            </p>
          </Card>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar title={t('counter_title')} sub={t('counter_sub')} rate={rate} />
      <div className="content">
        <div className="two">
          <div style={{ display: 'grid', gap: 18 }}>
            {/* piece */}
            <Card title={t('pieces_title')} right={piece && <span className={`tag ${statusTone}`}>{t(`piece_status_${status}`)}</span>}>
              <form className="toolbar" onSubmit={(e) => { e.preventDefault(); lookup(); }} style={{ marginBottom: 10 }}>
                <input placeholder={t('scan')} value={query} onChange={(e) => setQuery(e.target.value)} aria-label={t('scan')} autoFocus />
                <button className="btn ghost" type="submit">{t('find_piece')}</button>
                <label className="small">{t('dealer_discount')}
                  <select value={discount} onChange={(e) => changeDiscount(Number(e.target.value))} style={{ marginInlineStart: 8, minWidth: 80 }}>
                    {[0, 5, 10, 15, 20].map((d) => <option key={d} value={d}>{d}%</option>)}
                  </select>
                </label>
              </form>
              {pieceError && <ErrorBox error={pieceError} />}
              {piece && (
                <div className="two" style={{ gridTemplateColumns: '1fr 1fr' }}>
                  <dl className="dl">
                    <dt>{t('serial')}</dt><dd><b>{piece.serial}</b> · {piece.product?.name}</dd>
                    <dt>{t('karat')}</dt><dd>{piece.karat ? `${piece.karat}K` : '—'}</dd>
                    <dt>{t('gross')}</dt><dd className="num">{grams(piece.gross_weight_g, lang)}</dd>
                    <dt>{t('net')}</dt><dd className="num">{grams(piece.net_weight_g, lang)}</dd>
                    <dt>{t('rfid')}</dt><dd>{piece.rfid_tag ?? '—'}</dd>
                    {typeof piece.availability.detail === 'string' && <><dt>{t('state')}</dt><dd>{String(piece.availability.detail)} {piece.availability.client ? `· ${piece.availability.client.name}` : ''}</dd></>}
                  </dl>
                  {piece.breakdown ? (
                    <div className="bk">
                      <div className="ln"><span>{t('metal_value')}</span><span className="num">{money(piece.breakdown.metal_value, cur, lang)}</span></div>
                      <div className="ln"><span>{t('wastage_value')} ({pct(piece.wastage_pct, lang)})</span><span className="num">{money(piece.breakdown.wastage_value, cur, lang)}</span></div>
                      <div className="ln"><span>{t('making_charge')}{discount ? ` · −${pct(discount, lang)}` : ''}</span><span className="num">{money(piece.breakdown.making_charge, cur, lang)}</span></div>
                      <div className="ln"><span>{t('stones_value')}</span><span className="num">{money(piece.breakdown.stones_value, cur, lang)}</span></div>
                      <div className="ln"><span>{t('vat')}</span><span className="num">{money(piece.breakdown.vat, cur, lang)}</span></div>
                      <div className="ln total"><span>{t('total')}</span><span className="num">{money(piece.breakdown.total, cur, lang)}</span></div>
                    </div>
                  ) : <div className="err">{t('no_breakdown')}: {piece.breakdown_unavailable}</div>}
                </div>
              )}
            </Card>

            {/* client */}
            <Card title={t('client_context')} right={client && <button className="btn ghost" onClick={() => { setClient(null); setOldGold(null); }}>{t('change_client')}</button>}>
              {client ? (
                <div className="toolbar">
                  <b>{client.name}</b>
                  <TierTag tier={client.tier} label={tierLabel(lang, client.tier)} />
                  {client.discreet_billing && <span className="tag teal">{t('discreet_on')}</span>}
                  {client.no_marketing && <span className="tag">{t('no_marketing')}</span>}
                  <span className="small muted">{t('typical_budget')}: {money(client.typical_budget, cur, lang)} · {t('lifetime_value')}: {money(client.lifetime_value, cur, lang)} · {t('manager')}: {client.relationship_manager?.name ?? '—'}</span>
                  {client.restricted && <span className="small" style={{ color: 'var(--gold-dark)' }}>{t('restricted_note')}</span>}
                </div>
              ) : (
                <>
                  <div className="toolbar" style={{ marginBottom: 10 }}>
                    <input placeholder={t('search')} value={clientQ} onChange={(e) => setClientQ(e.target.value)} aria-label={t('pick_client')} />
                  </div>
                  {clients.loading ? <Loading /> : clients.data && (clients.data.items.length === 0 ? <Empty /> : (
                    <table className="tbl"><tbody>{clients.data.items.map((c) => (
                      <tr key={c.id} className="row" onClick={() => api.client(c.id).then((d) => setClient(d))}>
                        <td><b>{c.name}</b></td><td><TierTag tier={c.tier} label={tierLabel(lang, c.tier)} /></td>
                        <td className="r num">{money(c.lifetime_value, cur, lang)}</td>
                      </tr>))}</tbody></table>
                  ))}
                </>
              )}
            </Card>

            {/* old gold */}
            <Card title={t('old_gold_panel')} right={oldGold && <button className="btn ghost" onClick={() => setOldGold(null)}>{t('og_none')}</button>}>
              {oldGold ? (
                <div className="toolbar">
                  <b>{oldGold.name}</b>
                  <span className="num">{grams(oldGold.gross_weight_g, lang)} {oldGold.karat}K · {t('fine_weight')} {grams(oldGold.fine_weight_g, lang)} · {t('applied_rate')} {num(oldGold.applied_rate_per_g, lang)}/{t('unit_g')}</span>
                  <StateTag state={oldGold.state} label={stateLabel(lang, oldGold.state)} />
                  <b className="num">{t('og_value')}: {money(oldGold.value, cur, lang)}</b>
                  {oldGold.state === 'to_approve' && <><span className="small muted">{t('og_needs_approval')}</span><button className="btn ghost" disabled={ogBusy} onClick={approveIntake}>{t('og_approve')}</button></>}
                </div>
              ) : (
                <>
                  {intakes.data && intakes.data.items.length > 0 && (
                    <table className="tbl" style={{ marginBottom: 10 }}><tbody>{intakes.data.items.map((x) => (
                      <tr key={x.id} className="row" onClick={() => setOldGold(x)}>
                        <td><b>{x.name}</b></td><td className="num">{grams(x.gross_weight_g, lang)} {x.karat}K</td>
                        <td><StateTag state={x.state} label={stateLabel(lang, x.state)} /></td>
                        <td className="r num">{money(x.value, cur, lang)}</td>
                      </tr>))}</tbody></table>
                  )}
                  <div className="toolbar">
                    <span className="small"><b>{t('og_new')}</b></span>
                    <input type="number" step="0.001" min="0" placeholder={t('og_weight')} value={ogForm.weight} onChange={(e) => setOgForm({ ...ogForm, weight: e.target.value })} aria-label={t('og_weight')} style={{ minWidth: 150 }} />
                    <select value={ogForm.karat} onChange={(e) => setOgForm({ ...ogForm, karat: e.target.value })} aria-label={t('og_karat')} style={{ minWidth: 80 }}>{KARATS.map((k) => <option key={k} value={k}>{k}K</option>)}</select>
                    <input type="number" step="0.5" min="0" placeholder={t('og_melt')} value={ogForm.melt} onChange={(e) => setOgForm({ ...ogForm, melt: e.target.value })} aria-label={t('og_melt')} style={{ minWidth: 110 }} />
                    <input type="number" step="0.5" min="0" placeholder={t('og_buyback')} value={ogForm.buyback} onChange={(e) => setOgForm({ ...ogForm, buyback: e.target.value })} aria-label={t('og_buyback')} style={{ minWidth: 110 }} />
                    <button className="btn ghost" disabled={ogBusy || !ogForm.weight} onClick={createIntake}>{ogBusy ? t('working') : t('og_create')}</button>
                  </div>
                  <p className="small muted">{t('breakdown_sub')}</p>
                </>
              )}
              {ogError && <div style={{ marginTop: 10 }}><ErrorBox error={ogError} /></div>}
            </Card>
          </div>

          <div style={{ display: 'grid', gap: 18 }}>
            {/* readiness */}
            <Card title={t('readiness')}>
              {!readiness ? <Empty text="—" /> : (
                <div className="bk">
                  {readiness.checks.map((c) => (
                    <div className="ln" key={c.key}>
                      <span>{c.ok ? '✓' : '✗'} {t(`chk_${c.key}`)}</span>
                      <span className={`tag ${c.ok ? 'good' : 'bad'}`}>{c.ok ? 'OK' : (typeof c.detail === 'string' ? c.detail : (c.detail as { status?: string })?.status ? t(`piece_status_${(c.detail as { status: string }).status}`) : '—')}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* payment */}
            <Card title={t('payment')}>
              <div className="bk">
                <div className="ln"><span>{t('pieces_credit')}</span><span className="num">{money(pieces_total, cur, lang)}</span></div>
                {credit > 0 && <div className="ln"><span>{t('old_gold_credit')}</span><span className="num">− {money(credit, cur, lang)}</span></div>}
                <div className="ln total"><span>{t('amount_due')}</span><span className="num">{money(due, cur, lang)}</span></div>
              </div>
              <div className="toolbar" style={{ marginTop: 12 }}>
                <label className="small">{t('payment_method')}
                  <select value={journal} onChange={(e) => setJournal(Number(e.target.value))} style={{ marginInlineStart: 8, minWidth: 140 }}>
                    {methods.map((j) => <option key={j.id} value={j.id}>{j.name}</option>)}
                  </select>
                </label>
                <label className="small">{t('deposit')}
                  <input type="number" step="0.01" min="0" value={amount} placeholder={`${t('pay_full')}: ${money(due, cur, lang)}`} onChange={(e) => setAmount(e.target.value)} style={{ marginInlineStart: 8, minWidth: 180 }} />
                </label>
              </div>
              {commitError && <div style={{ marginTop: 12 }}><ErrorBox error={commitError} /></div>}
              <button className="btn" style={{ marginTop: 14, width: '100%' }} disabled={committing || !readiness?.ready || !piece || !client || !journal} onClick={() => setReviewing(true)}>
                {committing ? t('working') : t('review_commit')}
              </button>
              {client?.discreet_billing && <p className="small muted">{t('discreet_on')}</p>}
            </Card>
          </div>
        </div>

        {reviewing && piece && client && (
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="commit-title">
            <div className="card box"><div className="bd">
              <h3 id="commit-title">{t('commit_title')}</h3>
              <p className="muted">{t('commit_text')}</p>
              <p><b>{piece.serial}</b> · {client.name} · <span className="num">{money(due, cur, lang)}</span>{amount ? ` · ${t('deposit')} ${money(Number(amount), cur, lang)}` : ''}</p>
              <div className="toolbar">
                <button className="btn" onClick={commit}>{t('commit_yes')}</button>
                <button className="btn ghost" onClick={() => setReviewing(false)}>{t('cancel')}</button>
              </div>
            </div></div>
          </div>
        )}
      </div>
    </>
  );
}
