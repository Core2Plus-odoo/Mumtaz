import { useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { api, type Rate, type User } from '../lib/api';
import { tierLabel, useT } from '../lib/i18n';
import { money } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, TierTag, useLoad } from '../components/ui';

export default function Clients() {
  const { t, lang } = useT();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const nav = useNavigate();
  const [q, setQ] = useState('');
  const [tier, setTier] = useState('');
  const clients = useLoad(() => api.clients({ q, tier, limit: 100 }), [q, tier]);
  const cur = user.company.currency;
  return (
    <>
      <TopBar title={t('clients_title')} sub={t('clients_sub')} rate={rate} />
      <div className="content">
        <div className="toolbar">
          <input placeholder={t('search')} value={q} onChange={(e) => setQ(e.target.value)} aria-label={t('search')} />
          <select value={tier} onChange={(e) => setTier(e.target.value)} aria-label={t('tier')}>
            <option value="">{t('tier')}: {t('all')}</option>
            {['standard', 'preferred', 'private', 'royal'].map((k) => <option key={k} value={k}>{tierLabel(lang, k)}</option>)}
          </select>
          <span className="sp" />
          {clients.data && <span className="small muted num">{clients.data.total}</span>}
        </div>
        <Card title={t('clients_title')}>
          {clients.error && <ErrorBox error={clients.error} retry={clients.reload} />}
          {clients.loading ? <Loading /> : clients.data && (clients.data.items.length === 0 ? <Empty /> : (
            <table className="tbl">
              <thead><tr><th>{t('client')}</th><th>{t('tier')}</th><th>{t('manager')}</th><th>{t('ai_cap')}</th><th className="r">{t('lifetime_value')}</th></tr></thead>
              <tbody>
                {clients.data.items.map((c) => (
                  <tr key={c.id} className="row" onClick={() => nav(`/clients/${c.id}`)}>
                    <td><b>{c.name}</b>{c.city && <div className="small muted">{c.city}</div>}</td>
                    <td><TierTag tier={c.tier} label={tierLabel(lang, c.tier)} /></td>
                    <td>{c.relationship_manager?.name ?? '—'}</td>
                    <td className="small">{c.ai_autonomy_cap === 2 ? t('ai_cap_2') : t('ai_cap_3')}</td>
                    <td className="r num">{money(c.lifetime_value, cur, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ))}
        </Card>
      </div>
    </>
  );
}
