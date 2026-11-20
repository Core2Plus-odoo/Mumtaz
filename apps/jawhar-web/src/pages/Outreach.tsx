// Outreach: the occasions coming up with each client's consent and the
// draft for it; the approved drafts a person sends from her own phone; and
// the record of what was sent. Nothing on this page sends a message: the
// send button opens the approved text in the person's own app.
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, type Consent, type OutreachDraft, type OutreachDraftDetail, type Upcoming } from '../lib/api';
import { useT } from '../lib/i18n';
import { when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, useLoad } from '../components/ui';

export function ConsentTag({ consent, t }: { consent: Consent; t: (k: string) => string }) {
  const cls = consent.status === 'given' && !consent.no_marketing ? 'ok' : consent.status === 'withdrawn' || consent.no_marketing ? 'bad' : '';
  return <span className={`tag ${cls}`}>{t(`consent_${consent.no_marketing && consent.status !== 'withdrawn' ? 'withdrawn' : consent.status}`)}</span>;
}

export default function Outreach() {
  const { t, lang } = useT();
  const [params, setParams] = useSearchParams();
  const upcoming = useLoad(() => api.outreachUpcoming());
  const ready = useLoad(() => api.outreachDrafts('approved'));
  const [showSent, setShowSent] = useState(true);
  const sent = useLoad(() => api.outreachDrafts('sent'));
  const selectedId = Number(params.get('draft') || 0) || null;
  const [draft, setDraft] = useState<OutreachDraftDetail | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: 'ok' | 'warn'; text: string } | null>(null);
  useEffect(() => {
    if (!selectedId) { setDraft(null); return; }
    api.outreachDraft(selectedId).then((d) => { setDraft(d); setNotice(null); }).catch(() => setDraft(null));
  }, [selectedId]);
  const reloadAll = () => { upcoming.reload(); ready.reload(); sent.reload(); };
  const prepare = async (occasion_id?: number) => {
    setBusy(true); setNotice(null);
    try {
      const out = await api.outreachPrepare(occasion_id ? { occasion_id } : {});
      if (out.refused) { setNotice({ kind: 'warn', text: out.message ?? out.refused }); return; }
      setNotice({ kind: 'ok', text: `${out.count} ${t('prepared_n')}` });
      reloadAll();
      if (out.count === 1) setParams({ draft: String(out.prepared[0].id) });
    } catch (e) { setNotice({ kind: 'warn', text: (e as Error).message }); }
    finally { setBusy(false); }
  };
  const send = async (channel: 'whatsapp' | 'email' | 'note') => {
    if (!draft) return;
    setBusy(true); setNotice(null);
    try {
      const out = await api.outreachSend(draft.id, { channel, note: note || undefined });
      if (out.handoff.url) window.open(out.handoff.url, '_blank', 'noopener');
      setDraft(out.draft); setNote('');
      setNotice({ kind: 'ok', text: t('sent_done') });
      reloadAll();
    } catch (e) { setNotice({ kind: 'warn', text: (e as Error).message }); }
    finally { setBusy(false); }
  };
  const kindLabel = (k: string) => t(`occ_${k}`);
  const stateLabel = (s: string) => t(`dstate_${s}`);
  const row = (u: Upcoming) => (
    <tr key={u.occasion_id} className={u.due ? '' : 'muted'}>
      <td><b><Link to={`/clients/${u.client.id}`}>{u.client.name}</Link></b> {u.client.restricted && <span className="tag gold">VIP</span>}</td>
      <td>{kindLabel(u.kind)}</td>
      <td className="num">{when(u.date, lang, false)}<div className="small muted">{u.in_days === 0 ? t('today_word') : t('in_days').replace('{n}', String(u.in_days))}{u.due && <> · <b>{t('due_now')}</b></>}</div></td>
      <td><ConsentTag consent={u.consent} t={t} /></td>
      <td>{t(`channel_${u.channel}`)}</td>
      <td>{u.draft ? (
        <Link to={`/outreach?draft=${u.draft.id}`} className={selectedId === u.draft.id ? 'on' : ''}>{u.draft.name} · {stateLabel(u.draft.state)}</Link>
      ) : <span className="muted small">{t('no_draft_yet')}</span>}</td>
      <td className="r">{!u.draft && u.due && <button className="btn small ghost" disabled={busy} onClick={() => prepare(u.occasion_id)}>{t('prepare_one')}</button>}</td>
    </tr>
  );
  const draftRow = (d: OutreachDraft) => (
    <li key={d.id} className={selectedId === d.id ? 'on' : ''} onClick={() => setParams({ draft: String(d.id) })}>
      <div><b>{d.client?.name ?? '—'}</b>{d.restricted && <span className="tag gold" style={{ marginInlineStart: 6 }}>VIP</span>} · {t(`channel_${d.channel}`)}</div>
      <div className="small muted">{d.name} · {d.occasion ? kindLabel(d.occasion.kind) : t('draft_followup')} · {d.state === 'sent' ? `${t('sent_by')} ${d.sent_by?.name ?? '—'} · ${when(d.sent_at, lang)}` : `${t('approved_ready').split('.')[0]} · ${d.approved_by?.name ?? ''}`}</div>
    </li>
  );
  const up = upcoming.data;
  return (
    <>
      <TopBar title={t('outreach_title')} sub={t('outreach_sub')}>
        <button className="btn" disabled={busy} onClick={() => prepare()}>{busy ? t('working') : t('prepare_due')}</button>
      </TopBar>
      <div className="content">
        {notice && <div className={`notice ${notice.kind}`}>{notice.text}</div>}
        <Card title={t('upcoming_occasions')} sub={up ? `${up.count} · ${up.due} ${t('due_now').toLowerCase()} · ${t('consent_rule')}` : undefined}>
          {upcoming.error && <ErrorBox error={upcoming.error} retry={upcoming.reload} />}
          {upcoming.loading && !up ? <Loading /> : up && (
            up.items.length === 0 ? <Empty text={t('outreach_empty')} /> : (
              <table className="tbl outreach">
                <thead><tr><th>{t('clients_title')}</th><th>{t('occasion')}</th><th>{t('date')}</th><th>{t('consent')}</th><th>{t('channel_possible')}</th><th>{t('draft_state')}</th><th></th></tr></thead>
                <tbody>{up.items.map(row)}</tbody>
              </table>
            )
          )}
        </Card>
        <div className="two">
          <div style={{ display: 'grid', gap: 18 }}>
            <Card title={t('ready_to_send')}>
              {ready.error && <ErrorBox error={ready.error} retry={ready.reload} />}
              {ready.loading && !ready.data ? <Loading /> : ready.data && (
                ready.data.items.length === 0 ? <Empty /> : <ul className="worklist">{ready.data.items.map(draftRow)}</ul>
              )}
            </Card>
            <Card title={t('sent_log')} right={<button className="btn ghost small" onClick={() => setShowSent(!showSent)}>{showSent ? t('hide_sent') : t('show_sent')}</button>}>
              {showSent && (sent.loading && !sent.data ? <Loading /> : sent.data && (
                sent.data.items.length === 0 ? <Empty /> : <ul className="worklist">{sent.data.items.map(draftRow)}</ul>
              ))}
            </Card>
          </div>
          <Card title={t('selected_draft')} sub={draft ? `${draft.name} · ${draft.policy_version}` : undefined}>
            {!draft ? <Empty text={t('select_a_draft')} /> : (
              <div className="draft">
                <div className="kv">
                  <div><span className="muted">{t('recipient')}</span><b>{draft.client ? <Link to={`/clients/${draft.client.id}`}>{draft.client.name}</Link> : '—'}</b></div>
                  <div><span className="muted">{t('consent')}</span><b>{draft.consent ? <ConsentTag consent={draft.consent} t={t} /> : '—'}</b></div>
                  <div><span className="muted">{t('channel_possible')}</span><b>{t(`channel_${draft.channel}`)}</b></div>
                  <div><span className="muted">{t('state')}</span><b>{stateLabel(draft.state)}</b></div>
                </div>
                {draft.reasons.length > 0 && (
                  <div><div className="muted small">{t('why_now')}</div><ul className="plain">{draft.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul></div>
                )}
                <div className="muted small">{t('exact_payload')}</div>
                <textarea className="payload" value={draft.body} readOnly rows={7} dir="auto" />
                {draft.state === 'pending' && <div className="notice warn"><Link to={`/agents?draft=${draft.id}`}>{t('review_draft')} → {t('nav_agents')}</Link></div>}
                {draft.state === 'approved' && (
                  <>
                    <div className="notice ok">{t('approved_ready')} {draft.approved_by?.name} · {when(draft.approved_at, lang)}</div>
                    {draft.consent && !draft.consent.may_message && <div className="notice warn">{t('consent_rule')} <Link to={`/clients/${draft.client?.id}`}>{t('consent_record')} →</Link></div>}
                    <input className="payload" placeholder={t('send_note_ph')} value={note} onChange={(e) => setNote(e.target.value)} />
                    <div className="actions">
                      {draft.consent?.may_message && draft.client && (
                        <>
                          <button className="btn" disabled={busy || !draft.consent.may_message} onClick={() => send('whatsapp')}>{t('send_whatsapp')}</button>
                          <button className="btn ghost" disabled={busy || !draft.consent.may_message} onClick={() => send('email')}>{t('send_email')}</button>
                        </>
                      )}
                      <button className="btn ghost" disabled={busy} onClick={() => send('note')}>{t('mark_called')}</button>
                    </div>
                    <p className="small muted">{t('sent_how')}</p>
                  </>
                )}
                {draft.state === 'sent' && (
                  <div className="notice ok">{t('sent_by')} {draft.sent_by?.name ?? '—'} · {t(`channel_${draft.sent_channel ?? 'note'}`)} · {when(draft.sent_at, lang)}{draft.send_note && <> · {draft.send_note}</>}</div>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
