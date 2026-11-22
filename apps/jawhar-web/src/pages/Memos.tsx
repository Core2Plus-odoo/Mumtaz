import { useNavigate, useOutletContext } from 'react-router-dom';
import { api, type Rate, type User } from '../lib/api';
import { stateLabel, useT } from '../lib/i18n';
import { money, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, StateTag, useLoad } from '../components/ui';

export default function Memos() {
  const { t, lang } = useT();
  const nav = useNavigate();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const memos = useLoad(() => api.memos());
  const cur = user.company.currency;
  return (
    <>
      <TopBar title={t('memos_title')} sub={t('memos_sub')} rate={rate} />
      <div className="content">
        <Card title={t('memos_title')}>
          {memos.error && <ErrorBox error={memos.error} retry={memos.reload} />}
          {memos.loading ? <Loading /> : memos.data && (memos.data.items.length === 0 ? <Empty /> : (
            <table className="tbl">
              <thead><tr><th>{t('number')}</th><th>{t('client')}</th><th>{t('pieces_title')}</th><th>{t('date')}</th><th>{t('return_by')}</th><th>{t('state')}</th><th className="r">{t('insured')}</th></tr></thead>
              <tbody>{memos.data.items.map((m) => (
                <tr key={m.id} className="row" onClick={() => m.client && nav(`/clients/${m.client.id}`)}>
                  <td><b>{m.name}</b></td><td>{m.client?.name}</td>
                  <td>{m.pieces.map((p) => <a key={p.id} href="#" onClick={(e) => { e.preventDefault(); e.stopPropagation(); nav(`/pieces/${p.id}`); }}>{p.serial} </a>)}</td>
                  <td className="num">{when(m.date_out, lang, false)}</td><td className="num">{when(m.return_by, lang, false)}</td>
                  <td><StateTag state={m.state} label={stateLabel(lang, m.state)} /></td>
                  <td className="r num">{money(m.insured_value, cur, lang)}</td>
                </tr>))}</tbody>
            </table>
          ))}
        </Card>
      </div>
    </>
  );
}
