import { Link, useOutletContext } from 'react-router-dom';
import { api, type Rate, type User } from '../lib/api';
import { useT } from '../lib/i18n';
import { money, num, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, ErrorBox, Kpi, Loading, useLoad } from '../components/ui';
import { CardGrid } from './Cards';

export default function Today() {
  const { t, lang } = useT();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const today = useLoad(() => api.today());
  const cards = useLoad(() => api.cards('open'));
  const cur = user.company.currency;
  const d = today.data;
  const na = (v: unknown) => v === null || v === undefined;

  return (
    <>
      <TopBar title={t('today_title')} sub={t('today_sub')} rate={rate} />
      <div className="content">
        {today.error && <ErrorBox error={today.error} retry={today.reload} />}
        {today.loading && <Loading />}
        {d && (
          <div className="kpis">
            <Kpi label={t('rate_24k')} na={!d.rate}
              value={d.rate ? `${num(d.rate.rate_per_gram, lang)} ${d.rate.currency}` : t('rate_none')}
              sub={d.rate ? `${t('rate_by')} ${d.rate.approved_by?.name ?? '—'} · ${when(d.rate.approved_at ?? d.rate.effective_at, lang)}` : undefined} />
            <Kpi label={t('pieces_on_hand')} na={na(d.pieces_on_hand)}
              value={na(d.pieces_on_hand) ? t('not_visible') : num(d.pieces_on_hand, lang, 0)}
              sub={na(d.stock_value_incl_vat) ? undefined : `${t('stock_value')}: ${money(d.stock_value_incl_vat, cur, lang)}`} />
            <Kpi label={t('open_quotes')} na={na(d.open_quotes)} value={na(d.open_quotes) ? t('not_visible') : num(d.open_quotes, lang, 0)} />
            <Kpi label={t('orders_month')} na={!d.orders_this_month}
              value={d.orders_this_month ? num(d.orders_this_month.count, lang, 0) : t('not_visible')}
              sub={d.orders_this_month ? money(d.orders_this_month.amount, cur, lang) : undefined} />
            <Kpi label={t('unpaid')} na={!d.invoices_unpaid}
              value={d.invoices_unpaid ? num(d.invoices_unpaid.count, lang, 0) : t('not_visible')}
              sub={d.invoices_unpaid ? money(d.invoices_unpaid.amount, cur, lang) : undefined} />
            <Kpi label={t('memos_out')} na={na(d.memos_out)} value={na(d.memos_out) ? t('not_visible') : num(d.memos_out, lang, 0)} />
            <Kpi label={t('old_gold_pending')} na={na(d.old_gold_pending)} value={na(d.old_gold_pending) ? t('not_visible') : num(d.old_gold_pending, lang, 0)} />
            <Kpi label={t('clients_total')} na={!d.clients}
              value={d.clients ? num(d.clients.total, lang, 0) : t('not_visible')}
              sub={d.clients ? `${t('clients_restricted')}: ${num(d.clients.restricted, lang, 0)}` : undefined} />
          </div>
        )}
        <Card title={t('cards_title')} sub={t('cards_sub')} right={<Link to="/cards" className="small">{t('nav_cards')} →</Link>}>
          {cards.error && <ErrorBox error={cards.error} retry={cards.reload} />}
          {cards.loading ? <Loading /> : cards.data && <CardGrid cards={cards.data.items.slice(0, 6)} />}
        </Card>
      </div>
    </>
  );
}
