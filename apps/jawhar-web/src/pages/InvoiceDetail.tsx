import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { api, type Rate } from '../lib/api';
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
  const m = inv.data;
  return (
    <>
      <TopBar title={m?.name ?? t('loading')} sub={<Link to="/invoices">← {t('invoices_title')}</Link> } rate={rate}>
        {m && <><StateTag state={m.state} label={stateLabel(lang, m.state)} /> <StateTag state={m.payment_state} label={stateLabel(lang, m.payment_state)} /></>}
      </TopBar>
      <div className="content">
        {inv.error && <ErrorBox error={inv.error} retry={inv.reload} />}
        {inv.loading && !m && <Loading />}
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
          </Card>
        )}
      </div>
    </>
  );
}
