import { useOutletContext } from 'react-router-dom';
import { api, type Rate, type User } from '../lib/api';
import { stateLabel, useT } from '../lib/i18n';
import { grams, money, num, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, StateTag, useLoad } from '../components/ui';

export default function OldGold() {
  const { t, lang } = useT();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const og = useLoad(() => api.oldGold());
  const cur = user.company.currency;
  return (
    <>
      <TopBar title={t('old_gold_title')} sub={t('old_gold_sub')} rate={rate} />
      <div className="content">
        <Card title={t('old_gold_title')}>
          {og.error && <ErrorBox error={og.error} retry={og.reload} />}
          {og.loading ? <Loading /> : og.data && (og.data.items.length === 0 ? <Empty /> : (
            <table className="tbl">
              <thead><tr><th>{t('number')}</th><th>{t('client')}</th><th>{t('date')}</th><th>{t('karat')}</th><th className="r">{t('gross')}</th><th className="r">{t('fine_weight')}</th><th className="r">{t('applied_rate')}</th><th className="r">{t('value')}</th><th>{t('state')}</th></tr></thead>
              <tbody>{og.data.items.map((x) => (
                <tr key={x.id}>
                  <td><b>{x.name}</b></td><td>{x.client?.name ?? '—'}</td><td className="num">{when(x.date, lang, false)}</td><td>{x.karat}K</td>
                  <td className="r num">{grams(x.gross_weight_g, lang)}</td><td className="r num">{grams(x.fine_weight_g, lang)}</td>
                  <td className="r num">{num(x.applied_rate_per_g, lang)}</td><td className="r num"><b>{money(x.value, cur, lang)}</b></td>
                  <td><StateTag state={x.state} label={stateLabel(lang, x.state)} /></td>
                </tr>))}</tbody>
            </table>
          ))}
        </Card>
      </div>
    </>
  );
}
