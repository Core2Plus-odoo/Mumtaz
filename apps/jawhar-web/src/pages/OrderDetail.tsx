import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { api, type Rate, type Snapshot } from '../lib/api';
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

export default function OrderDetail() {
  const { id } = useParams();
  const { t, lang } = useT();
  const nav = useNavigate();
  const { rate } = useOutletContext<{ rate: Rate | null }>();
  const order = useLoad(() => api.order(Number(id)), [id]);
  const o = order.data;
  return (
    <>
      <TopBar title={o?.name ?? t('loading')} sub={<Link to="/documents">← {t('documents_title')}</Link> } rate={rate}>
        {o && <StateTag state={o.state} label={stateLabel(lang, o.state)} />}
      </TopBar>
      <div className="content">
        {order.error && <ErrorBox error={order.error} retry={order.reload} />}
        {order.loading && !o && <Loading />}
        {o && (
          <Card title={`${o.client?.name ?? ''} · ${when(o.date, lang)}`} sub={o.kind === 'quote' ? t('repriceable') : t('frozen')}
            right={<span className="num"><b>{money(o.amount_total, o.currency, lang)}</b> <span className="small muted">({t('vat')} {money(o.amount_tax, o.currency, lang)})</span></span>}>
            <table className="tbl">
              <thead><tr><th>{t('product')}</th><th>{t('serial')}</th><th className="r">{t('dealer_discount')}</th><th className="r">{t('subtotal')}</th><th className="r">{t('total')}</th></tr></thead>
              <tbody>{(o.lines ?? []).map((l) => (
                <tr key={l.id}>
                  <td>{l.description}{l.snapshot && <SnapshotBox s={l.snapshot} currency={o.currency} />}</td>
                  <td>{l.piece ? <a href="#" onClick={(e) => { e.preventDefault(); nav(`/pieces/${l.piece!.id}`); }}>{l.piece.serial}</a> : '—'}</td>
                  <td className="r num">{l.making_discount_pct ? pct(l.making_discount_pct, lang) : '—'}</td>
                  <td className="r num">{money(l.subtotal, o.currency, lang)}</td>
                  <td className="r num"><b>{money(l.total, o.currency, lang)}</b></td>
                </tr>))}</tbody>
            </table>
            {o.invoices && o.invoices.length > 0 && (
              <div style={{ marginTop: 12 }} className="small">{t('invoices_title')}: {o.invoices.map((i) => i && <Link key={i.id} to={`/invoices/${i.id}`}>{i.name}</Link>)}</div>
            )}
          </Card>
        )}
      </div>
    </>
  );
}
