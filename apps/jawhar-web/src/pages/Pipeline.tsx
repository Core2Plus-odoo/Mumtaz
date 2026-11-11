import { useNavigate, useOutletContext } from 'react-router-dom';
import { api, type Rate } from '../lib/api';
import { useT } from '../lib/i18n';
import { money, num, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Kpi, Loading, useLoad } from '../components/ui';

/** Odds come from Odoo's own scoring on your closed business; nothing here is typed. */
export default function Pipeline() {
  const { t, lang } = useT();
  const nav = useNavigate();
  const { rate } = useOutletContext<{ rate: Rate | null }>();
  const pipe = useLoad(() => api.pipeline());
  const p = pipe.data;
  return (
    <>
      <TopBar title={t('pipeline_title')} sub={t('pipeline_sub')} rate={rate} />
      <div className="content">
        {pipe.error && <ErrorBox error={pipe.error} retry={pipe.reload} />}
        {pipe.loading && <Loading />}
        {p && (
          <>
            <div className="kpis">
              <Kpi label={t('open_opps')} value={num(p.summary.open, lang, 0)} sub={money(p.summary.open_value, p.summary.currency, lang)} />
              <Kpi label={t('weighted')} value={money(p.summary.weighted, p.summary.currency, lang)} />
              <Kpi label={t('won_value')} value={money(p.summary.won_value, p.summary.currency, lang)} />
            </div>
            <div className="kpis">
              {p.stages.map((s) => (
                <div key={s.id} className="kpi">
                  <small>{s.name}</small>
                  <b className="num">{num(s.count, lang, 0)}</b>
                  <div className="sub num">{money(s.value, p.summary.currency, lang)}{!s.won && ` · ${t('weighted').toLowerCase()} ${money(s.weighted, p.summary.currency, lang)}`}</div>
                </div>
              ))}
            </div>
            <Card title={t('pipeline_title')}>
              {p.items.length === 0 ? <Empty /> : (
                <table className="tbl">
                  <thead><tr><th>{t('client')}</th><th>{t('stage')}</th><th className="r">{t('amount')}</th><th className="r">{t('odds')}</th><th>{t('salesperson')}</th><th>{t('next')}</th></tr></thead>
                  <tbody>{p.items.map((l) => (
                    <tr key={l.id} className="row" onClick={() => (l.tray ? nav(`/trays/${l.tray.id}`) : l.client && nav(`/clients/${l.client.id}`))}>
                      <td><b>{l.client?.name ?? l.name}</b><div className="small muted">{l.name}</div></td>
                      <td><span className={`tag ${l.stage.won ? 'good' : 'teal'}`}>{l.stage.name}</span></td>
                      <td className="r num">{money(l.expected_revenue, l.currency, lang)}</td>
                      <td className="r num">{num(l.probability, lang, 0)}%{l.automated ? '' : ' *'}</td>
                      <td>{l.salesperson?.name ?? '—'}</td>
                      <td className="small">{l.next_activity ? `${l.next_activity.summary} · ${when(l.next_activity.date, lang, false)}` : <span className="muted">{t('nothing_scheduled')}</span>}</td>
                    </tr>))}</tbody>
                </table>
              )}
            </Card>
          </>
        )}
      </div>
    </>
  );
}
