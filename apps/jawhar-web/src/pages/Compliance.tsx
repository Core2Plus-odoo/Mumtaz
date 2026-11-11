// Compliance: the cash threshold the named finance manager confirms (empty
// until then: nothing here is validated law), the record of every identity
// check, screening and threshold crossing, and the documents about to
// expire. The counter reads the same values; this page only shows them.
import { useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { api, type AmlConfig, type Rate } from '../lib/api';
import { useT } from '../lib/i18n';
import { money, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, useLoad } from '../components/ui';

export function KycTag({ status, t }: { status: string; t: (k: string) => string }) {
  const cls = status === 'verified' ? 'ok' : status === 'none' ? '' : 'bad';
  return <span className={`tag ${cls}`}>{t(`kyc_${status}`)}</span>;
}

export default function Compliance() {
  const { t, lang } = useT();
  const { rate } = useOutletContext<{ rate: Rate | null }>();
  const cfg = useLoad(() => api.amlConfig());
  const events = useLoad(() => api.amlEvents({ limit: 60 }));
  const expiring = useLoad(() => api.amlExpiring(30));
  const [threshold, setThreshold] = useState('');
  const [window_, setWindow] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'warn'; text: string } | null>(null);
  const c: AmlConfig | undefined = cfg.data;
  const save = async (value: number) => {
    setBusy(true); setMsg(null);
    try {
      await api.amlSetConfig({ threshold: value, window_days: window_ ? Number(window_) : undefined, note: note || undefined });
      setMsg({ kind: 'ok', text: t('saved') }); setThreshold(''); setNote('');
      cfg.reload(); events.reload();
    } catch (e) { setMsg({ kind: 'warn', text: (e as Error).message }); }
    finally { setBusy(false); }
  };
  return (
    <>
      <TopBar title={t('compliance_title')} sub={t('compliance_sub')} rate={rate} />
      <div className="content">
        <div className="two">
          <Card title={t('aml_threshold')} sub={c ? (c.configured ? `${t('aml_confirmed_by')} ${c.confirmed_by?.name ?? '—'} · ${when(c.confirmed_at, lang)}` : undefined) : undefined}>
            {cfg.error && <ErrorBox error={cfg.error} retry={cfg.reload} />}
            {cfg.loading && !c ? <Loading /> : c && (
              <div className="kyc">
                {c.configured ? (
                  <dl className="dl">
                    <dt>{t('aml_threshold')}</dt><dd className="num"><b>{money(c.threshold, c.currency, lang)}</b></dd>
                    <dt>{t('aml_window')}</dt><dd className="num">{c.window_days} {t('days_word')}</dd>
                    {c.note && <><dt>{t('note')}</dt><dd>{c.note}</dd></>}
                  </dl>
                ) : <div className="notice warn">{t('aml_not_set')}</div>}
                <p className="small muted">{t('kyc_rule')}</p>
                {c.can_configure ? (
                  <div className="actions">
                    <input type="number" min="0" step="1" placeholder={`${t('aml_threshold')} (${c.currency})`} value={threshold} onChange={(e) => setThreshold(e.target.value)} />
                    <input type="number" min="1" max="3660" placeholder={`${t('aml_window')}: ${c.window_days} ${t('days_word')}`} value={window_} onChange={(e) => setWindow(e.target.value)} />
                    <input placeholder={t('aml_note_ph')} value={note} onChange={(e) => setNote(e.target.value)} style={{ flex: 1 }} />
                    <button className="btn" disabled={busy || !threshold} onClick={() => save(Number(threshold))}>{t('aml_confirm')}</button>
                    {c.configured && <button className="btn ghost" disabled={busy} onClick={() => save(0)}>{t('aml_remove')}</button>}
                  </div>
                ) : <p className="small muted">{t('aml_set_hint')}</p>}
                {msg && <div className={`notice ${msg.kind}`}>{msg.text}</div>}
              </div>
            )}
          </Card>
          <Card title={t('aml_expiring')}>
            {expiring.error && <ErrorBox error={expiring.error} retry={expiring.reload} />}
            {expiring.loading && !expiring.data ? <Loading /> : expiring.data && (
              expiring.data.items.length === 0 ? <Empty /> : (
                <table className="tbl"><tbody>{expiring.data.items.map((k) => (
                  <tr key={k.client?.id}><td><b><Link to={`/clients/${k.client?.id}`}>{k.client?.name}</Link></b> {k.restricted && <span className="tag gold">VIP</span>}</td>
                    <td>{k.id_type ? t(`doc_${k.id_type}`) : '—'} · {k.id_last4}</td>
                    <td className="num">{when(k.id_expiry, lang, false)}</td>
                    <td><KycTag status={k.status} t={t} /></td></tr>))}</tbody></table>
              )
            )}
          </Card>
        </div>
        <Card title={t('aml_events')}>
          {events.error && <ErrorBox error={events.error} retry={events.reload} />}
          {events.loading && !events.data ? <Loading /> : events.data && (
            events.data.items.length === 0 ? <Empty /> : (
              <table className="tbl">
                <thead><tr><th>{t('date')}</th><th>{t('kind')}</th><th>{t('clients_title')}</th><th className="r">{t('cash_now')}</th><th className="r">{t('cash_before')}</th><th className="r">{t('aml_threshold')}</th><th>{t('identity')}</th><th>{t('rate_by')}</th><th>{t('note')}</th></tr></thead>
                <tbody>{events.data.items.map((e) => (
                  <tr key={e.id}>
                    <td className="num">{when(e.at, lang)}</td>
                    <td><span className={`tag ${e.kind === 'refused' ? 'bad' : e.kind === 'threshold_crossed' ? 'warn' : ''}`}>{t(`ev_${e.kind}`)}</span></td>
                    <td>{e.client ? <Link to={`/clients/${e.client.id}`}>{e.client.name}</Link> : '—'}{e.order && <span className="small muted"> · {e.order.name}</span>}</td>
                    <td className="r num">{e.amount_cash ? money(e.amount_cash, e.currency, lang) : '—'}</td>
                    <td className="r num">{e.cash_window_before ? money(e.cash_window_before, e.currency, lang) : '—'}</td>
                    <td className="r num">{e.threshold ? money(e.threshold, e.currency, lang) : '—'}</td>
                    <td className="small">{e.kyc.id_type ? `${t(`doc_${e.kyc.id_type}`)} · ${e.kyc.id_last4}` : e.kyc.screening ? t(`scr_${e.kyc.screening}`) : '—'}</td>
                    <td>{e.by?.name}</td>
                    <td className="small muted">{e.note ?? ''}</td>
                  </tr>))}</tbody>
              </table>
            )
          )}
        </Card>
      </div>
    </>
  );
}
