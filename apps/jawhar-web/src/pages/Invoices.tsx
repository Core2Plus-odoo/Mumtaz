import { useNavigate, useOutletContext } from 'react-router-dom';
import { api, type Rate } from '../lib/api';
import { stateLabel, useT } from '../lib/i18n';
import { money, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, StateTag, useLoad } from '../components/ui';

export default function Invoices() {
  const { t, lang } = useT();
  const { rate } = useOutletContext<{ rate: Rate | null }>();
  const nav = useNavigate();
  const inv = useLoad(() => api.invoices({ limit: 100 }));
  return (
    <>
      <TopBar title={t('invoices_title')} sub={t('invoices_sub')} rate={rate} />
      <div className="content">
        <Card title={t('invoices_title')}>
          {inv.error && <ErrorBox error={inv.error} retry={inv.reload} />}
          {inv.loading ? <Loading /> : inv.data && (inv.data.items.length === 0 ? <Empty /> : (
            <table className="tbl">
              <thead><tr><th>{t('number')}</th><th>{t('client')}</th><th>{t('date')}</th><th>{t('due')}</th><th>{t('state')}</th><th>{t('payment_state')}</th><th className="r">{t('amount')}</th><th className="r">{t('residual')}</th></tr></thead>
              <tbody>{inv.data.items.map((m) => (
                <tr key={m.id} className="row" onClick={() => nav(`/invoices/${m.id}`)}>
                  <td><b>{m.name}</b></td><td>{m.client?.name}</td><td className="num">{when(m.date, lang, false)}</td><td className="num">{when(m.due_date, lang, false)}</td>
                  <td><StateTag state={m.state} label={stateLabel(lang, m.state)} /></td>
                  <td><StateTag state={m.payment_state} label={stateLabel(lang, m.payment_state)} /></td>
                  <td className="r num"><b>{money(m.amount_total, m.currency, lang)}</b></td>
                  <td className="r num">{money(m.amount_residual, m.currency, lang)}</td>
                </tr>))}</tbody>
            </table>
          ))}
        </Card>
      </div>
    </>
  );
}
