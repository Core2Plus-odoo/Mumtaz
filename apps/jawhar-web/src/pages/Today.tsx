// Today (plan v3 wireframe 20): the command bar, Zayan's brief, what waits
// for a person, then the figures and the owner's cards. Every figure is
// displayed as the engine returned it.
import { useState } from 'react';
import { Link, useNavigate, useOutletContext } from 'react-router-dom';
import { api, type AskResult, type Brief, type Rate, type User } from '../lib/api';
import { useT } from '../lib/i18n';
import { money, num, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, ErrorBox, Kpi, Loading, useLoad } from '../components/ui';
import { CardGrid } from './Cards';

export default function Today() {
  const { t, lang } = useT();
  const nav = useNavigate();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const today = useLoad(() => api.today());
  const cards = useLoad(() => api.cards('open'));
  const queue = useLoad(() => api.aiQueue());
  const cur = user.company.currency;
  const d = today.data;
  const na = (v: unknown) => v === null || v === undefined;

  const [ask, setAsk] = useState('');
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<AskResult | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [briefErr, setBriefErr] = useState<string | null>(null);

  const prepareBrief = async () => {
    setAsking(true); setBriefErr(null);
    try { const b = await api.aiBrief(); if (b.refused) setBriefErr(b.message ?? b.refused); else setBrief(b); }
    catch (e) { setBriefErr((e as Error).message); }
    finally { setAsking(false); }
  };
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ask.trim()) return;
    setAsking(true); setAnswer(null);
    try {
      const out = await api.aiAsk(ask.trim());
      setAnswer(out);
      if (out.brief && !out.refused) setBrief(out.brief);
      if (out.intent === 'tray' && out.tray_id) nav(`/trays/${out.tray_id}`);
      else if (out.intent === 'followup' && out.draft_id) nav(`/agents?draft=${out.draft_id}`);
    } catch (err) { setAnswer({ intent: 'error', agent: 'zayan', client: null, message: (err as Error).message }); }
    finally { setAsking(false); }
  };

  return (
    <>
      <TopBar title={t('today_title')} sub={t('today_sub')} rate={rate} />
      <div className="content">
        <form className="askbar" onSubmit={submit}>
          <input value={ask} onChange={(e) => setAsk(e.target.value)} placeholder={t('ask_placeholder')} dir="auto" aria-label={t('ask')} />
          <button className="btn" disabled={asking}>{asking ? t('ask_working') : t('ask')}</button>
        </form>
        {answer && (answer.message || answer.rate || answer.queue) && (
          <div className={`notice askresult ${answer.refused || answer.intent === 'error' ? 'warn' : ''}`}>
            {answer.message && <div>{answer.message}</div>}
            {answer.rate && <div>{num(answer.rate.rate_per_gram, lang)} {answer.rate.currency} · {answer.rate.approved_by} · {when(answer.rate.approved_at, lang)}</div>}
            {answer.queue && <ul className="queue">{answer.queue.map((q) => <li key={`${q.kind}${q.id}`}><span>{q.title}</span><span className="muted small">{q.next}</span></li>)}</ul>}
          </div>
        )}
        <div className="two">
          <Card title={t('brief_title')} sub={t('brief_level')} right={<button className="btn ghost small" disabled={asking} onClick={prepareBrief}>{t('brief_prepare')}</button>}>
            {briefErr && <div className="notice warn">{briefErr}</div>}
            {!brief && !briefErr && <p className="muted small">{t('today_sub')}</p>}
            {brief && (
              <div className="brief">
                {brief.sentences.map((s, i) => <p key={i} dir="auto">{s}</p>)}
                <div className="muted small">
                  {t('brief_read_from')} {when(brief.as_of, lang)} · {brief.narrated_by === 'local' ? t('brief_narrated_local') : `${t('brief_narrated_model')} ${brief.narrated_by}`} · {t('level_b')}
                </div>
              </div>
            )}
          </Card>
          <Card title={t('waiting_title')} sub={t('waiting_sub')} right={<Link to="/agents" className="small">{t('open_inbox')} →</Link>}>
            {queue.error && <ErrorBox error={queue.error} retry={queue.reload} />}
            {queue.loading && !queue.data ? <Loading /> : queue.data && (
              queue.data.refused ? <div className="notice warn">{queue.data.message}</div> :
              queue.data.items.length === 0 ? <p className="muted small">{t('empty')}</p> : (
                <ul className="queue">
                  {queue.data.items.map((q) => (
                    <li key={`${q.kind}${q.id}`}>
                      <span>
                        {q.kind === 'draft' ? <Link to={`/agents?draft=${q.id}`}>{q.title}</Link> : q.title}
                        {q.detail && <div className="muted small">{q.detail}</div>}
                      </span>
                      <span className="small muted" style={{ textAlign: 'end' }}>{q.next}<br />{q.owner}</span>
                    </li>
                  ))}
                </ul>
              )
            )}
          </Card>
        </div>
        {today.error && <ErrorBox error={today.error} retry={today.reload} />}
        {today.loading && <Loading />}
        {d && (
          <div className="kpis">
            <Kpi label={t('rate_24k')} na={!d.rate}
              value={d.rate ? `${num(d.rate.rate_per_gram, lang)} ${d.rate.currency}` : t('rate_none')}
              sub={d.rate ? `${t('rate_by')} ${d.rate.approved_by?.name ?? '—'} · ${when(d.rate.approved_at ?? d.rate.effective_at, lang)}` : undefined} />
            <Kpi label={t('pieces_on_hand')} na={na(d.pieces_on_hand)}
              value={na(d.pieces_on_hand) ? t('not_visible') : num(d.pieces_on_hand, lang, 0)}
              sub={na(d.stock_value_incl_vat) ? undefined : `${t('stock_value')}: ${money(d.stock_value_incl_vat, cur, lang)}`} />
            <Kpi label={t('open_quotes')} na={na(d.open_quotes)} value={na(d.open_quotes) ? t('not_visible') : num(d.open_quotes, lang, 0)} />
            <Kpi label={t('orders_month')} na={!d.orders_this_month}
              value={d.orders_this_month ? num(d.orders_this_month.count, lang, 0) : t('not_visible')}
              sub={d.orders_this_month ? money(d.orders_this_month.amount, cur, lang) : undefined} />
            <Kpi label={t('unpaid')} na={!d.invoices_unpaid}
              value={d.invoices_unpaid ? num(d.invoices_unpaid.count, lang, 0) : t('not_visible')}
              sub={d.invoices_unpaid ? money(d.invoices_unpaid.amount, cur, lang) : undefined} />
            <Kpi label={t('memos_out')} na={na(d.memos_out)} value={na(d.memos_out) ? t('not_visible') : num(d.memos_out, lang, 0)} />
            <Kpi label={t('old_gold_pending')} na={na(d.old_gold_pending)} value={na(d.old_gold_pending) ? t('not_visible') : num(d.old_gold_pending, lang, 0)} />
            <Kpi label={t('clients_total')} na={!d.clients}
              value={d.clients ? num(d.clients.total, lang, 0) : t('not_visible')}
              sub={d.clients ? `${t('clients_restricted')}: ${num(d.clients.restricted, lang, 0)}` : undefined} />
          </div>
        )}
        <Card title={t('cards_title')} sub={t('cards_sub')} right={<Link to="/cards" className="small">{t('nav_cards')} →</Link>}>
          {cards.error && <ErrorBox error={cards.error} retry={cards.reload} />}
          {cards.loading ? <Loading /> : cards.data && <CardGrid cards={cards.data.items.slice(0, 6)} />}
        </Card>
      </div>
    </>
  );
}
