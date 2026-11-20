import { useState } from 'react';
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { api, ApiError, type Order, type Rate, type Snapshot } from '../lib/api';
import { stateLabel, useT } from '../lib/i18n';
import { grams, money, num, pct, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, ErrorBox, Loading, StateTag, useLoad } from '../components/ui';

export function SnapshotBox({ s, currency }: { s: Snapshot; currency: string }) {
  const { t, lang } = useT();
  return (
    <div className="small muted" style={{ marginTop: 4 }}>
      {t('snapshot')}: {t('rate_per_gram')} {num(s.rate_per_gram, lang)}/{t('unit_g')} · {t('fine_weight')} {grams(s.fine_weight_g, lang)} ·
      {' '}{t('metal_value')} {money(s.metal_value, currency, lang)} · {t('wastage_value')} {money(s.wastage_value, currency, lang)} ·
      {' '}{t('making_charge')} {money(s.making_charge, currency, lang)} · {t('stones_value')} {money(s.stones_value, currency, lang)} ·
      {' '}{t('priced_on')} {when(s.priced_on, lang)}
    </div>
  );
}

/** One server action with busy/error/notice state. Level D: a person clicks. */
function useAction(onDone: (o: Order) => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const run = async (fn: () => Promise<Order>): Promise<boolean> => {
    setBusy(true); setError(null);
    try { onDone(await fn()); return true; }
    catch (e) { setError(e instanceof ApiError ? e : (e as Error)); return false; }
    finally { setBusy(false); }
  };
  return { busy, error, run, clear: () => setError(null) };
}

export default function OrderDetail() {
  const { id } = useParams();
  const { t, lang } = useT();
  const nav = useNavigate();
  const { rate } = useOutletContext<{ rate: Rate | null }>();
  const order = useLoad(() => api.order(Number(id)), [id]);
  const [local, setLocal] = useState<Order | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [invoicing, setInvoicing] = useState(false);
  const [invError, setInvError] = useState<Error | null>(null);
  const act = useAction((o) => { setLocal(o); });
  const o = local ?? order.data;
  const hasMargin = !!o?.lines?.some((l) => l.margin !== null && l.margin !== undefined);

  const confirm = () => { setConfirming(false); act.run(() => api.confirmQuote(o!.id)).then((ok) => ok && setNotice(t('done_confirmed'))); };
  const renew = () => act.run(() => api.renewQuote(o!.id));
  const invoice = async () => {
    setInvoicing(true); setInvError(null);
    try { const inv = await api.invoiceOrder(o!.id); setNotice(t('done_invoiced')); nav(`/invoices/${inv.id}`); }
    catch (e) { setInvError(e instanceof ApiError ? e : (e as Error)); }
    finally { setInvoicing(false); }
  };

  return (
    <>
      <TopBar title={o?.name ?? t('loading')} sub={<Link to="/documents">← {t('documents_title')}</Link>} rate={rate}>
        {o && <StateTag state={o.state} label={stateLabel(lang, o.state)} />}
        {o?.kind === 'quote' && o.expired && <span className="tag bad">{t('expired')}</span>}
      </TopBar>
      <div className="content">
        {order.error && <ErrorBox error={order.error} retry={order.reload} />}
        {order.loading && !o && <Loading />}
        {notice && <div className="tag good" role="status" style={{ justifySelf: 'start', padding: '8px 12px' }}>{notice}</div>}
        {o && (
          <Card title={`${o.client?.name ?? ''} · ${when(o.date, lang)}`}
            sub={o.kind === 'quote'
              ? `${t('repriceable')} · ${t('valid_until')} ${when(o.validity_date, lang, false)}`
              : t('frozen')}
            right={<span className="num"><b>{money(o.amount_total, o.currency, lang)}</b> <span className="small muted">({t('vat')} {money(o.amount_tax, o.currency, lang)})</span></span>}>
            <table className="tbl">
              <thead><tr><th>{t('product')}</th><th>{t('serial')}</th><th className="r">{t('dealer_discount')}</th><th className="r">{t('subtotal')}</th>{hasMargin && <th className="r">{t('margin')}</th>}<th className="r">{t('total')}</th></tr></thead>
              <tbody>{(o.lines ?? []).map((l) => (
                <tr key={l.id}>
                  <td>{l.description}{l.snapshot && <SnapshotBox s={l.snapshot} currency={o.currency} />}</td>
                  <td>{l.piece ? <a href="#" onClick={(e) => { e.preventDefault(); nav(`/pieces/${l.piece!.id}`); }}>{l.piece.serial}</a> : '—'}</td>
                  <td className="r num">{l.making_discount_pct ? pct(l.making_discount_pct, lang) : '—'}</td>
                  <td className="r num">{money(l.subtotal, o.currency, lang)}</td>
                  {hasMargin && <td className="r num">{l.margin === null || l.margin === undefined ? '—' : money(l.margin, o.currency, lang)}</td>}
                  <td className="r num"><b>{money(l.total, o.currency, lang)}</b></td>
                </tr>))}</tbody>
            </table>

            {(act.error || invError) && <div style={{ marginTop: 12 }}><ErrorBox error={(act.error || invError)!} /></div>}

            <div className="toolbar" style={{ marginTop: 14 }}>
              {o.kind === 'quote' && o.expired && (
                <button className="btn" disabled={act.busy} onClick={renew}>{act.busy ? t('working') : t('renew')}</button>
              )}
              {o.kind === 'quote' && !o.expired && (
                <button className="btn" disabled={act.busy} onClick={() => setConfirming(true)}>{act.busy ? t('working') : t('confirm_order')}</button>
              )}
              {o.kind === 'order' && o.invoice_status === 'to invoice' && (
                <button className="btn" disabled={invoicing} onClick={invoice}>{invoicing ? t('working') : t('create_invoice')}</button>
              )}
              {o.invoices && o.invoices.length > 0 && (
                <span className="small">{t('invoices_title')}: {o.invoices.map((i) => i && <Link key={i.id} to={`/invoices/${i.id}`} style={{ marginInlineEnd: 8 }}>{i.name}</Link>)}</span>
              )}
            </div>
          </Card>
        )}
        {confirming && o && (
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
            <div className="card box">
              <div className="bd">
                <h3 id="confirm-title">{t('confirm_title')}</h3>
                <p className="muted">{t('confirm_text')}</p>
                <p><b>{o.name}</b> · {o.client?.name} · <span className="num">{money(o.amount_total, o.currency, lang)}</span></p>
                <div className="toolbar">
                  <button className="btn" onClick={confirm}>{t('confirm_yes')}</button>
                  <button className="btn ghost" onClick={() => setConfirming(false)}>{t('cancel')}</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
