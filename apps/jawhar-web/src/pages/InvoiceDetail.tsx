import { useEffect, useState } from 'react';
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { api, ApiError, type Invoice, type PaymentMethod, type Rate } from '../lib/api';
import { stateLabel, useT } from '../lib/i18n';
import { money, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, ErrorBox, Loading, StateTag, useLoad } from '../components/ui';
import { SnapshotBox } from './OrderDetail';

export default function InvoiceDetail() {
  const { id } = useParams();
  const { t, lang } = useT();
  const nav = useNavigate();
  const { rate } = useOutletContext<{ rate: Rate | null }>();
  const inv = useLoad(() => api.invoice(Number(id)), [id]);
  const [local, setLocal] = useState<Invoice | null>(null);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [journal, setJournal] = useState<number | ''>('');
  const [amount, setAmount] = useState<string>('');
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const m = local ?? inv.data;
  const payable = !!m && m.state === 'posted' && (m.payment_state === 'not_paid' || m.payment_state === 'partial');

  useEffect(() => {
    if (payable && methods.length === 0) {
      api.paymentMethods().then((r) => { setMethods(r.items); if (r.items[0]) setJournal(r.items[0].id); }, () => {});
    }
  }, [payable, methods.length]);

  const pay = async () => {
    if (!m) return;
    setPaying(true); setError(null);
    try {
      const out = await api.payInvoice(m.id, { journal_id: journal || undefined, amount: amount ? Number(amount) : undefined });
      setLocal(out.invoice); setAmount(''); setNotice(t('done_paid'));
    } catch (e) { setError(e instanceof ApiError ? e : (e as Error)); }
    finally { setPaying(false); }
  };

  return (
    <>
      <TopBar title={m?.name ?? t('loading')} sub={<Link to="/invoices">← {t('invoices_title')}</Link>} rate={rate}>
        {m && <><StateTag state={m.state} label={stateLabel(lang, m.state)} /> <StateTag state={m.payment_state} label={stateLabel(lang, m.payment_state)} /></>}
      </TopBar>
      <div className="content">
        {inv.error && <ErrorBox error={inv.error} retry={inv.reload} />}
        {inv.loading && !m && <Loading />}
        {notice && <div className="tag good" role="status" style={{ justifySelf: 'start', padding: '8px 12px' }}>{notice}</div>}
        {m && (
          <Card title={`${m.client?.name ?? ''} · ${when(m.date, lang, false)}`} sub={m.origin ? `${t('orders')}: ${m.origin}` : undefined}
            right={<span className="num"><b>{money(m.amount_total, m.currency, lang)}</b> <span className="small muted">({t('vat')} {money(m.amount_tax, m.currency, lang)} · {t('residual')} {money(m.amount_residual, m.currency, lang)})</span></span>}>
            <table className="tbl">
              <thead><tr><th>{t('product')}</th><th>{t('serial')}</th><th className="r">{t('subtotal')}</th><th className="r">{t('total')}</th></tr></thead>
              <tbody>{(m.lines ?? []).map((l) => (
                <tr key={l.id}>
                  <td>{l.description}{l.snapshot && <SnapshotBox s={l.snapshot} currency={m.currency} />}</td>
                  <td>{l.piece ? <a href="#" onClick={(e) => { e.preventDefault(); nav(`/pieces/${l.piece!.id}`); }}>{l.piece.serial}</a> : '—'}</td>
                  <td className="r num">{money(l.subtotal, m.currency, lang)}</td>
                  <td className="r num"><b>{money(l.total, m.currency, lang)}</b></td>
                </tr>))}</tbody>
            </table>
            {payable && (
              <div className="toolbar" style={{ marginTop: 14 }} aria-label={t('register_payment')}>
                <label className="small">{t('payment_method')}
                  <select value={journal} onChange={(e) => setJournal(Number(e.target.value))} style={{ marginInlineStart: 8, minWidth: 160 }}>
                    {methods.map((j) => <option key={j.id} value={j.id}>{j.name}</option>)}
                  </select>
                </label>
                <label className="small">{t('pay_amount')}
                  <input type="number" step="0.01" min="0" max={m.amount_residual} value={amount}
                    placeholder={`${t('pay_full')}: ${money(m.amount_residual, m.currency, lang)}`}
                    onChange={(e) => setAmount(e.target.value)} style={{ marginInlineStart: 8, minWidth: 200 }} />
                </label>
                <button className="btn" disabled={paying || !journal} onClick={pay}>{paying ? t('working') : t('record_payment')}</button>
              </div>
            )}
            {error && <div style={{ marginTop: 12 }}><ErrorBox error={error} /></div>}
          </Card>
        )}
      </div>
    </>
  );
}
