import { useOutletContext } from 'react-router-dom';
import { api, type Rate } from '../lib/api';
import { stateLabel, useT } from '../lib/i18n';
import { num, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, StateTag, useLoad } from '../components/ui';

export default function Rates() {
  const { t, lang } = useT();
  const { rate } = useOutletContext<{ rate: Rate | null }>();
  const rates = useLoad(() => api.rates(50));
  return (
    <>
      <TopBar title={t('rates_title')} sub={t('rates_sub')} rate={rate} />
      <div className="content">
        <Card title={t('rate_history')}>
          {rates.error && <ErrorBox error={rates.error} retry={rates.reload} />}
          {rates.loading ? <Loading /> : rates.data && (rates.data.items.length === 0 ? <Empty /> : (
            <table className="tbl">
              <thead><tr><th>{t('rate_effective')}</th><th className="r">{t('rate_24k')}</th><th>{t('source')}</th><th>{t('rate_entered_by')}</th><th>{t('rate_by')}</th><th>{t('status')}</th></tr></thead>
              <tbody>{rates.data.items.map((r) => (
                <tr key={r.id}>
                  <td className="num">{when(r.effective_at, lang)}</td>
                  <td className="r num"><b>{num(r.rate_per_gram, lang)} {r.currency}</b></td>
                  <td>{r.source}</td><td>{r.created_by?.name ?? '—'}</td>
                  <td>{r.approved_by ? `${r.approved_by.name} · ${when(r.approved_at, lang)}` : '—'}</td>
                  <td><StateTag state={r.state} label={stateLabel(lang, r.state)} /></td>
                </tr>))}</tbody>
            </table>
          ))}
        </Card>
      </div>
    </>
  );
}
