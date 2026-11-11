import { useState } from 'react';
import { Link, useNavigate, useOutletContext } from 'react-router-dom';
import { api, type Rate } from '../lib/api';
import { stateLabel, useT } from '../lib/i18n';
import { money, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, StateTag, useLoad } from '../components/ui';

export default function Documents() {
  const { t, lang } = useT();
  const { rate } = useOutletContext<{ rate: Rate | null }>();
  const nav = useNavigate();
  const [tab, setTab] = useState<'quotes' | 'orders'>('quotes');
  const docs = useLoad(() => (tab === 'quotes' ? api.quotes({ limit: 100 }) : api.orders({ limit: 100 })), [tab]);
  return (
    <>
      <TopBar title={t('documents_title')} sub={t('documents_sub')} rate={rate}>
        <Link to="/documents/new" className="btn">{t('new_quote')}</Link>
      </TopBar>
      <div className="content">
        <div className="tabs">
          <button className={tab === 'quotes' ? 'on' : ''} onClick={() => setTab('quotes')}>{t('quotes')}</button>
          <button className={tab === 'orders' ? 'on' : ''} onClick={() => setTab('orders')}>{t('orders')}</button>
        </div>
        <Card title={tab === 'quotes' ? t('quotes') : t('orders')} sub={tab === 'quotes' ? t('repriceable') : t('frozen')}>
          {docs.error && <ErrorBox error={docs.error} retry={docs.reload} />}
          {docs.loading ? <Loading /> : docs.data && (docs.data.items.length === 0 ? <Empty /> : (
            <table className="tbl">
              <thead><tr><th>{t('number')}</th><th>{t('client')}</th><th>{t('date')}</th><th>{t('salesperson')}</th><th>{t('state')}</th><th className="r">{t('lines')}</th><th className="r">{t('amount')}</th></tr></thead>
              <tbody>{docs.data.items.map((o) => (
                <tr key={o.id} className="row" onClick={() => nav(`/documents/${o.id}`)}>
                  <td><b>{o.name}</b></td><td>{o.client?.name}</td><td className="num">{when(o.date, lang, false)}</td>
                  <td>{o.salesperson?.name ?? '—'}</td><td><StateTag state={o.state} label={stateLabel(lang, o.state)} /></td>
                  <td className="r num">{o.line_count}</td><td className="r num"><b>{money(o.amount_total, o.currency, lang)}</b></td>
                </tr>))}</tbody>
            </table>
          ))}
        </Card>
      </div>
    </>
  );
}
