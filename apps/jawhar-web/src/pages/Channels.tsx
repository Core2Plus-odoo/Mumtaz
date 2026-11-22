// Channels: the gold rate feed (it only ever drafts; a different person
// approves on Gold rates), the web shelf's publication switches (the kiosk
// is the storefront, in the store and on the web), and requests by channel.
import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { api, type RateFeed, type Rate, type User } from '../lib/api';
import { useT } from '../lib/i18n';
import { num, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, useLoad } from '../components/ui';

export default function Channels() {
  const { t, lang } = useT();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const feed = useLoad(() => api.channelFeed());
  const shelf = useLoad(() => api.channelShelf());
  const reqs = useLoad(() => api.channelRequests(30));
  const [form, setForm] = useState<Partial<RateFeed>>({ provider: 'fixture', unit: 'gram_24k', fixture_value: 0, min_change_pct: 0, url: '', json_path: '' });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'warn'; text: string } | null>(null);
  const isManager = user.roles.includes('jewellery_manager');
  useEffect(() => { if (feed.data?.feed) setForm({ ...feed.data.feed }); }, [feed.data?.feed?.id]);
  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    setBusy(true); setMsg(null);
    try { await fn(); if (ok) setMsg({ kind: 'ok', text: ok }); feed.reload(); shelf.reload(); }
    catch (e) { setMsg({ kind: 'warn', text: (e as Error).message }); }
    finally { setBusy(false); }
  };
  const fetchNow = () => run(async () => {
    const out = await api.channelFeedFetch();
    setMsg(out.ok ? { kind: 'ok', text: out.skipped ? t(`feed_skipped_${out.skipped}`) : `${t('feed_drafted')}: ${num(out.rate_per_gram ?? 0, lang, 2)} ${rate?.currency ?? ''}` } : { kind: 'warn', text: out.error ?? '' });
  });
  const f = feed.data?.feed ?? null;
  return (
    <>
      <TopBar title={t('channels_title')} sub={t('channels_sub')} rate={rate} />
      <div className="content">
        {msg && <div className={`notice ${msg.kind}`}>{msg.text}</div>}
        <div className="two">
          <Card title={t('rate_feed')} sub={f ? `${t('feed_last')}: ${f.last_fetched_at ? when(f.last_fetched_at, lang) : '—'}${f.last_value ? ` · ${num(f.last_value, lang, 2)}` : ''}${f.last_error ? ` · ${f.last_error}` : ''}` : undefined}>
            {feed.error && <ErrorBox error={feed.error} retry={feed.reload} />}
            {feed.loading && !feed.data ? <Loading /> : (
              <div className="kyc">
                <p className="small muted">{t('feed_rule')}</p>
                {!f && <div className="notice warn">{t('feed_no_feed')}</div>}
                {f?.last_rate && <div className={`notice ${f.last_rate.state === 'draft' ? 'warn' : 'ok'}`}>{t('feed_drafted')}: <span className="num">{num(f.last_rate.rate_per_gram, lang, 2)}</span> · {t(`state_${f.last_rate.state}`)} · <Link to="/rates">{t('nav_rates')} →</Link></div>}
                {isManager && (
                  <>
                    <div className="actions">
                      <select value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value as RateFeed['provider'] })} aria-label={t('feed_provider')}>
                        <option value="fixture">{t('prov_fixture')}</option><option value="json_url">{t('prov_json_url')}</option>
                      </select>
                      <select value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value as RateFeed['unit'] })} aria-label={t('feed_unit')}>
                        <option value="gram_24k">{t('unit_gram_24k')}</option><option value="ounce_24k">{t('unit_ounce_24k')}</option>
                      </select>
                      <input type="number" step="0.01" min="0" placeholder={t('feed_min_change')} value={form.min_change_pct ?? 0} onChange={(e) => setForm({ ...form, min_change_pct: Number(e.target.value) })} style={{ width: 160 }} aria-label={t('feed_min_change')} />
                    </div>
                    {form.provider === 'fixture' ? (
                      <input type="number" step="0.0001" min="0" placeholder={t('feed_value')} value={form.fixture_value || ''} onChange={(e) => setForm({ ...form, fixture_value: Number(e.target.value) })} aria-label={t('feed_value')} />
                    ) : (
                      <div className="actions">
                        <input placeholder={`${t('feed_url')} (https://…)`} value={form.url ?? ''} onChange={(e) => setForm({ ...form, url: e.target.value })} style={{ flex: 2 }} aria-label={t('feed_url')} />
                        <input placeholder={`${t('feed_path')} (data.gold.usd_per_oz)`} value={form.json_path ?? ''} onChange={(e) => setForm({ ...form, json_path: e.target.value })} style={{ flex: 1 }} aria-label={t('feed_path')} />
                      </div>
                    )}
                    <div className="actions">
                      <button className="btn" disabled={busy} onClick={() => run(() => api.channelFeedSet({ ...form, name: form.name || 'Gold rate feed' }), t('saved'))}>{t('feed_save')}</button>
                      {f && <button className="btn ghost" disabled={busy} onClick={fetchNow}>{t('feed_fetch')}</button>}
                    </div>
                  </>
                )}
                {feed.data && feed.data.logs.length > 0 && (
                  <table className="tbl"><thead><tr><th>{t('feed_log')}</th><th className="r">{t('raw')}</th><th className="r">{t('rate_24k')}</th><th>{t('state')}</th></tr></thead>
                    <tbody>{feed.data.logs.slice(0, 8).map((l) => (
                      <tr key={l.id}><td className="num">{when(l.at, lang)}</td><td className="r num">{l.raw_value ? num(l.raw_value, lang, 2) : '—'}</td><td className="r num">{l.rate_per_gram ? num(l.rate_per_gram, lang, 2) : '—'}</td>
                        <td className="small">{l.error ? <span className="tag bad">{l.error}</span> : l.rate ? <span className={`tag ${l.rate.state === 'approved' ? 'ok' : 'warn'}`}>{t(`state_${l.rate.state}`)}</span> : l.note ? t(`feed_skipped_${l.note}`) : '—'}</td></tr>))}</tbody></table>
                )}
              </div>
            )}
          </Card>
          <Card title={t('requests_by_channel')} sub={t('last_30_days')}>
            {reqs.error && <ErrorBox error={reqs.error} retry={reqs.reload} />}
            {reqs.loading && !reqs.data ? <Loading /> : reqs.data && (
              <div className="storegrid">
                {(['store', 'web'] as const).map((ch) => { const c = reqs.data!.channels[ch]; return (
                  <div key={ch} className="storecard">
                    <h4>{t(`ch_${ch}`)}</h4>
                    <div><b className="num">{c.requests}</b> {t('kiosk_requests').toLowerCase()} · {c.viewing} {t('kiosk_ask_viewing').toLowerCase()} · {c.delivery} {t('kiosk_ask_delivery').toLowerCase()} · {c.confirmed} {t('confirmed_word')}</div>
                    {c.latest.length > 0 && <ul className="plain small muted">{c.latest.map((r) => <li key={r.id}>{r.name} · {r.serial} · {t(`kstate_${r.state}`) === `kstate_${r.state}` ? r.state : t(`kstate_${r.state}`)}</li>)}</ul>}
                  </div>); })}
                <div className="small"><a href="/app/kiosk" target="_blank" rel="noreferrer">{t('open_kiosk')} →</a></div>
              </div>
            )}
          </Card>
        </div>
        <Card title={t('web_shelf')} sub={shelf.data ? `${shelf.data.public_count} ${t('public_pieces')} · ${t('web_shelf_sub')}` : undefined}>
          {shelf.error && <ErrorBox error={shelf.error} retry={shelf.reload} />}
          {shelf.loading && !shelf.data ? <Loading /> : shelf.data && (
            shelf.data.items.length === 0 ? <Empty /> : (
              <div className="shelfgrid">
                {shelf.data.items.map((d) => (
                  <label key={d.id} className={`shelfcard ${d.published ? '' : 'off'}`}>
                    <span><b>{d.name}</b><div className="small muted">{d.category ? t(`cat_${d.category}`) : '—'} · {d.on_shelf} {t('on_shelf_n')}{!d.has_photo && ' · ∅'}</div></span>
                    <input type="checkbox" className="switch" checked={d.published} disabled={busy || !isManager} onChange={(e) => run(() => api.channelPublish(d.id, e.target.checked))} aria-label={`${d.name}: ${t('published')}`} />
                  </label>
                ))}
              </div>
            )
          )}
        </Card>
      </div>
    </>
  );
}
