import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { api, type Rate, type User } from '../lib/api';
import { stateLabel, tierLabel, useT } from '../lib/i18n';
import { money, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, StateTag, TierTag, useLoad } from '../components/ui';
import { useState } from 'react';

export default function ClientDetail() {
  const { id } = useParams();
  const { t, lang } = useT();
  const nav = useNavigate();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const client = useLoad(() => api.client(Number(id)), [id]);
  const cur = user.company.currency;
  const c = client.data;
  const [preparing, setPreparing] = useState(false);
  const prepare = async () => {
    if (!c) return;
    setPreparing(true);
    try { const tray = await api.createTray({ client_id: c.id, build: !c.restricted, limit: 3 }); nav(`/trays/${tray.id}`); }
    finally { setPreparing(false); }
  };
  const [laylaMsg, setLaylaMsg] = useState<string | null>(null);
  const followup = async () => {
    if (!c) return;
    setPreparing(true);
    try {
      const out = await api.aiLaylaFollowup({ client_id: c.id, channel: c.no_marketing ? 'note' : 'whatsapp' });
      if (out.refused) { setLaylaMsg(`${t('layla_refused')}: ${out.message}`); return; }
      nav(`/agents?draft=${out.draft.id}`);
    } finally { setPreparing(false); }
  };
  return (
    <>
      <TopBar title={c?.name ?? t('loading')} sub={<Link to="/clients">← {t('clients_title')}</Link> } rate={rate}>
        {c && <TierTag tier={c.tier} label={tierLabel(lang, c.tier)} />}
        {c && <button className="btn" disabled={preparing} onClick={prepare}>{preparing ? t('working') : t('prepare_tray')}</button>}
        {c && <button className="btn ghost" disabled={preparing} onClick={followup}>{t('ask_layla_followup')}</button>}
      </TopBar>
      {laylaMsg && <div className="content" style={{ paddingBottom: 0 }}><div className="notice warn">{laylaMsg}</div></div>}
      <div className="content">
        {client.error && <ErrorBox error={client.error} retry={client.reload} />}
        {client.loading && !c && <Loading />}
        {c && (
          <div className="two">
            <div style={{ display: 'grid', gap: 18 }}>
              <Card title={t('recent_orders')}>
                {c.orders.length === 0 ? <Empty /> : (
                  <table className="tbl">
                    <thead><tr><th>{t('number')}</th><th>{t('date')}</th><th>{t('state')}</th><th className="r">{t('amount')}</th></tr></thead>
                    <tbody>{c.orders.map((o) => (
                      <tr key={o.id} className="row" onClick={() => nav(`/documents/${o.id}`)}>
                        <td><b>{o.name}</b></td><td className="num">{when(o.date, lang, false)}</td>
                        <td><StateTag state={o.state} label={stateLabel(lang, o.state)} /></td>
                        <td className="r num">{money(o.amount_total, o.currency, lang)}</td>
                      </tr>))}</tbody>
                  </table>
                )}
              </Card>
              <Card title={t('trays')}>
                {c.trays.length === 0 ? <Empty /> : (
                  <table className="tbl"><tbody>{c.trays.map((tr) => (
                    <tr key={tr.id} className="row" onClick={() => nav(`/trays/${tr.id}`)}>
                      <td><b>{tr.name}</b></td><td>{t(`tray_state_${tr.state}`)}</td><td className="num">{tr.piece_count}</td>
                      <td className="r num">{money(tr.total, cur, lang)}</td></tr>))}</tbody></table>
                )}
              </Card>
              <Card title={t('memos_title')}>
                {c.memos.length === 0 ? <Empty /> : (
                  <table className="tbl"><tbody>{c.memos.map((m) => (
                    <tr key={m.id}><td><b>{m.name}</b></td><td>{m.pieces.map((p) => p.serial).join(', ')}</td>
                      <td className="num">{t('return_by')} {when(m.return_by, lang, false)}</td>
                      <td><StateTag state={m.state} label={stateLabel(lang, m.state)} /></td>
                      <td className="r num">{money(m.insured_value, cur, lang)}</td></tr>))}</tbody></table>
                )}
              </Card>
            </div>
            <Card title={t('clients_sub')}>
              <dl className="dl">
                <dt>{t('tier')}</dt><dd><TierTag tier={c.tier} label={tierLabel(lang, c.tier)} /> {c.restricted && <span className="tag gold">{t('restricted')}</span>}</dd>
                <dt>{t('manager')}</dt><dd>{c.relationship_manager?.name ?? '—'}</dd>
                <dt>{t('deputy')}</dt><dd>{c.deputy?.name ?? '—'}</dd>
                <dt>{t('ai_cap')}</dt><dd>{c.ai_autonomy_cap === 2 ? t('ai_cap_2') : t('ai_cap_3')}</dd>
                <dt>{t('lifetime_value')}</dt><dd className="num">{money(c.lifetime_value, cur, lang)}</dd>
                <dt>{t('preferred_karats')}</dt><dd>{c.preferred_karats ? c.preferred_karats.split(',').map((k) => `${k.trim()}K`).join(' · ') : '—'}</dd>
                <dt>{t('typical_budget')}</dt><dd className="num">{money(c.typical_budget, cur, lang)}</dd>
                <dt>{t('taste')}</dt><dd>{c.taste_notes ?? '—'}</dd>
                <dt>{t('occasions')}</dt><dd>{c.occasions.length ? c.occasions.map((o) => <div key={o.id}>{o.kind} · {when(o.date, lang, false)}</div>) : '—'}</dd>
                <dt>{t('no_marketing')}</dt><dd>{c.no_marketing ? '✓' : '—'}</dd>
                <dt>{t('discreet')}</dt><dd>{c.discreet_billing ? '✓' : '—'}</dd>
                <dt>{t('login')}</dt><dd>{c.email ?? '—'}{c.phone ? ` · ${c.phone}` : ''}</dd>
              </dl>
            </Card>
          </div>
        )}
      </div>
    </>
  );
}
