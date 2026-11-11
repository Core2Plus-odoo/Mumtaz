// Agent work and approvals (plan v3 wireframe 29): the team and its limits,
// the pending work, the selected draft with its exact text, and the review
// that binds to that text. Nothing on this page sends a message.
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, type Draft, type DraftDetail } from '../lib/api';
import { useT } from '../lib/i18n';
import { when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, useLoad } from '../components/ui';
import { Portrait, talkTo, type AgentKey } from '../components/AgentChat';

export default function Agents() {
  const { t, lang } = useT();
  const [params, setParams] = useSearchParams();
  const status = useLoad(() => api.aiStatus());
  const [showAll, setShowAll] = useState(false);
  const drafts = useLoad(() => api.aiDrafts(showAll ? 'all' : 'pending'), [showAll]);
  const runs = useLoad(() => api.aiRuns());
  const selectedId = Number(params.get('draft') || 0) || null;
  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [text, setText] = useState('');
  const [notice, setNotice] = useState<{ kind: 'ok' | 'warn'; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!selectedId) { setDraft(null); return; }
    api.aiDraft(selectedId).then((d) => { setDraft(d); setText(d.body); setNotice(null); }).catch(() => setDraft(null));
  }, [selectedId]);

  const select = (d: Draft) => setParams({ draft: String(d.id) });
  const refresh = (d: DraftDetail) => { setDraft(d); setText(d.body); drafts.reload(); status.reload(); runs.reload(); };
  const act = async (fn: () => Promise<DraftDetail>, ok?: string) => {
    setBusy(true); setNotice(null);
    try { const d = await fn(); refresh(d); if (ok) setNotice({ kind: 'ok', text: ok }); }
    catch (e) { setNotice({ kind: 'warn', text: (e as Error).message }); }
    finally { setBusy(false); }
  };
  const togglePause = async () => {
    if (!status.data) return;
    setBusy(true);
    try { await api.aiPause(!status.data.paused); status.reload(); } finally { setBusy(false); }
  };
  const levelLabel = (l: string) => t(`level_${l.toLowerCase()}`);
  const stateLabel = (s: string) => t(`dstate_${s}`);
  const kindLabel = (k: string) => (k === 'tray' ? t('draft_tray') : t('draft_followup'));
  const st = status.data;
  const changed = draft ? text !== draft.body : false;

  return (
    <>
      <TopBar title={t('agents_title')} sub={t('agents_sub')}>
        {st?.paused && <span className="tag bad">{t('paused')}</span>}
        {st?.can_pause && (
          <button className="btn ghost" disabled={busy} onClick={togglePause}>{st.paused ? t('resume_ai') : t('pause_ai')}</button>
        )}
      </TopBar>
      <div className="content">
        {status.error && <ErrorBox error={status.error} retry={status.reload} />}
        <Card title={t('team_status')} sub={st ? (st.model.configured ? `${t('model_on')} · ${st.model.name}` : t('model_off')) : undefined}>
          {status.loading && !st ? <Loading /> : st && (
            <div className="agents">
              {st.agents.map((a) => (
                <div key={a.key} className="agent">
                  <div className="agent-head">
                    <Portrait agent={a.key as AgentKey} size={56} />
                    <div><b>{a.name}</b><span className="muted"> · {a.role}</span>
                      <div><button className="btn small" onClick={() => talkTo(a.key as AgentKey)}>{t('talk_to')} {a.name}{st.voice?.[a.key] ? ' 🎤' : ''}</button></div>
                    </div>
                  </div>
                  <p className="muted small">{a.purpose}</p>
                  <div className="levels">
                    {['A', 'B', 'C', 'D', 'E'].map((l) => (
                      <span key={l} className={`lvl ${l <= a.ceiling ? 'on' : ''} ${l === 'E' ? 'off' : ''}`}>{levelLabel(l)}</span>
                    ))}
                  </div>
                  <div className="small muted">{a.runs_today} {t('runs_today')} · {a.waiting} {t('waiting_title').toLowerCase()} · {t('ceiling')} {a.ceiling}</div>
                </div>
              ))}
            </div>
          )}
        </Card>
        <div className="two">
          <Card title={t('pending_work')} right={<button className="btn ghost small" onClick={() => setShowAll(!showAll)}>{showAll ? t('waiting_title') : t('show_all')}</button>}>
            {drafts.error && <ErrorBox error={drafts.error} retry={drafts.reload} />}
            {drafts.loading && !drafts.data ? <Loading /> : drafts.data && (
              drafts.data.items.length === 0 ? <Empty /> : (
                <ul className="worklist">
                  {drafts.data.items.map((d) => (
                    <li key={d.id} className={selectedId === d.id ? 'on' : ''} onClick={() => select(d)}>
                      <div><b>{kindLabel(d.kind)}</b> · {d.client?.name ?? '—'}{d.restricted && <span className="tag gold" style={{ marginInlineStart: 6 }}>VIP</span>}</div>
                      <div className="small muted">{d.agent === 'layla' ? 'Layla' : 'Zayan'} · {stateLabel(d.state)} · {d.model_used === 'local' ? t('run_local') : d.model_used} · {when(d.created_at, lang)}</div>
                      {d.reasons[0] && <div className="small">{d.reasons[0]}</div>}
                    </li>
                  ))}
                </ul>
              )
            )}
          </Card>
          <Card title={t('selected_draft')} sub={draft ? `${draft.name} · ${draft.policy_version}` : undefined}>
            {!draft ? <Empty text={t('select_a_draft')} /> : (
              <div className="draft">
                <div className="kv">
                  <div><span className="muted">{t('recipient')}</span><b>{draft.client ? <Link to={`/clients/${draft.client.id}`}>{draft.client.name}</Link> : '—'}</b></div>
                  <div><span className="muted">{t('human_owner')}</span><b>{draft.owner?.name}</b></div>
                  <div><span className="muted">{t('channel_note')} / {t('channel_whatsapp')}</span><b>{t(`channel_${draft.channel}`)}</b></div>
                  <div><span className="muted">{t('state')}</span><b>{stateLabel(draft.state)}</b></div>
                </div>
                {draft.reasons.length > 0 && (
                  <div><div className="muted small">{t('why_now')}</div><ul className="plain">{draft.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul></div>
                )}
                <div>
                  <div className="muted small">{t('exact_payload')}</div>
                  <textarea className="payload" rows={7} value={text} onChange={(e) => setText(e.target.value)}
                    disabled={busy || !['pending', 'returned', 'approved'].includes(draft.state)} dir="auto" />
                  {changed && <div className="small warn-text">{t('changed_needs_review')}</div>}
                </div>
                {draft.tray_detail && (
                  <div className="small"><Link to={`/trays/${draft.tray_detail.id}`}>{t('open_tray')} → {draft.tray_detail.name}</Link></div>
                )}
                {!draft.consent_ok && <div className="notice warn">{t('no_consent')}</div>}
                {draft.state === 'approved' && <div className="notice ok">{t('approved_ready')} {draft.approved_by?.name} · {when(draft.approved_at, lang)}</div>}
                {notice && <div className={`notice ${notice.kind}`}>{notice.text}</div>}
                <div className="actions">
                  {changed && <button className="btn ghost" disabled={busy} onClick={() => act(() => api.aiDraftEdit(draft.id, text))}>{t('save_text')}</button>}
                  {draft.state === 'pending' && !changed && (
                    <button className="btn" disabled={busy || !draft.consent_ok} onClick={() => act(() => api.aiDraftApprove(draft.id, draft.body_digest), t('approved_ready'))}>{t('approve_draft')}</button>
                  )}
                  {['pending', 'approved'].includes(draft.state) && (
                    <button className="btn ghost" disabled={busy} onClick={() => act(() => api.aiDraftReturn(draft.id))}>{t('return_for_edit')}</button>
                  )}
                  {draft.state !== 'dismissed' && (
                    <button className="btn ghost" disabled={busy} onClick={() => act(() => api.aiDraftDismiss(draft.id))}>{t('dismiss')}</button>
                  )}
                </div>
                <div className="muted small">{t('sources')}: {draft.sources.join(' · ') || '—'}</div>
              </div>
            )}
          </Card>
        </div>
        <Card title={t('recent_runs')}>
          {runs.loading && !runs.data ? <Loading /> : runs.data && (
            runs.data.items.length === 0 ? <Empty /> : (
              <table className="tbl">
                <thead><tr><th>{t('date')}</th><th>Agent</th><th>Tool</th><th>Level</th><th>{t('state')}</th><th>Model</th><th>Tokens</th></tr></thead>
                <tbody>{runs.data.items.map((r) => (
                  <tr key={r.id} className={r.status === 'refused' ? 'refused' : ''}>
                    <td>{when(r.at, lang)}</td><td>{r.agent === 'layla' ? 'Layla' : 'Zayan'}</td><td>{r.tool}</td><td>{levelLabel(r.level)}</td>
                    <td>{r.status === 'refused' ? <span className="tag bad">{t('run_refused')} · {r.reason}</span> : r.status}</td>
                    <td>{r.model_used === 'local' ? t('run_local') : r.model_used}</td><td className="r">{r.input_tokens + r.output_tokens || '—'}</td>
                  </tr>
                ))}</tbody>
              </table>
            )
          )}
        </Card>
      </div>
    </>
  );
}
