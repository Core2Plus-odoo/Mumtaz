// Clients (plan wireframe 24, the list): search by name, phone or email;
// tier; sort; pages of 25; the next occasion and the relationship manager
// in the row; a New client form. A Private or Royal client appears only to
// the people the record rule allows, exactly as in Odoo.
import { useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { api, type NewClient, type Rate, type User } from '../lib/api';
import { tierLabel, useT } from '../lib/i18n';
import { money } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, TierTag, useLoad } from '../components/ui';

const PAGE = 25;

export default function Clients() {
  const { t, lang } = useT();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const nav = useNavigate();
  const [q, setQ] = useState('');
  const [tier, setTier] = useState('');
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(0);
  const [adding, setAdding] = useState(false);
  const clients = useLoad(() => api.clients({ q, tier, sort, limit: PAGE, offset: page * PAGE }), [q, tier, sort, page]);
  const cur = user.company.currency;
  const total = clients.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE));
  const occ = (c: { next_occasion: { kind: string; date: string; in_days: number } | null }) =>
    c.next_occasion ? `${t(`occ_${c.next_occasion.kind}`) === `occ_${c.next_occasion.kind}` ? c.next_occasion.kind : t(`occ_${c.next_occasion.kind}`)} · ${c.next_occasion.in_days === 0 ? t('today_word') : t('in_days').replace('{n}', String(c.next_occasion.in_days))}` : '—';
  const canVip = user.roles.includes('vip_manager');

  return (
    <>
      <TopBar title={t('clients_title')} sub={t('clients_sub')} rate={rate}>
        <button className="btn" onClick={() => setAdding(true)}>{t('new_client')}</button>
      </TopBar>
      <div className="content">
        <div className="toolbar">
          <input placeholder={t('search_clients')} value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} aria-label={t('search_clients')} />
          <select value={tier} onChange={(e) => { setTier(e.target.value); setPage(0); }} aria-label={t('tier')}>
            <option value="">{t('tier')}: {t('all')}</option>
            {['standard', 'preferred', 'private', 'royal'].map((k) => <option key={k} value={k}>{tierLabel(lang, k)}</option>)}
          </select>
          <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(0); }} aria-label={t('sort')}>
            <option value="name">{t('sort')}: {t('sort_name')}</option>
            <option value="value">{t('sort')}: {t('sort_value')}</option>
            <option value="recent">{t('sort')}: {t('sort_recent')}</option>
          </select>
          <span className="sp" />
          {clients.data && <span className="small muted num">{total}</span>}
        </div>
        <Card title={t('clients_title')} right={pages > 1 ? (
          <div className="pager">
            <button className="btn ghost small" disabled={page === 0} onClick={() => setPage(page - 1)}>{t('prev')}</button>
            <span className="small muted">{page + 1} {t('page_of')} {pages}</span>
            <button className="btn ghost small" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>{t('next_page')}</button>
          </div>) : undefined}>
          {clients.error && <ErrorBox error={clients.error} retry={clients.reload} />}
          {clients.loading && !clients.data ? <Loading /> : clients.data && (clients.data.items.length === 0 ? <Empty /> : (
            <table className="tbl">
              <thead><tr><th>{t('client')}</th><th>{t('tier')}</th><th>{t('phone')}</th><th>{t('next_occasion')}</th><th>{t('manager')}</th><th className="r">{t('lifetime_value')}</th></tr></thead>
              <tbody>
                {clients.data.items.map((c) => (
                  <tr key={c.id} className="row" onClick={() => nav(`/clients/${c.id}`)}>
                    <td><b>{c.name}</b>{c.city && <div className="small muted">{c.city}{c.lang === 'ar_001' ? ' · ع' : ''}</div>}</td>
                    <td><TierTag tier={c.tier} label={tierLabel(lang, c.tier)} />{c.no_marketing && <div className="small muted">{t('no_marketing_label')}</div>}</td>
                    <td className="small">{c.phone ?? '—'}</td>
                    <td className="small">{occ(c)}</td>
                    <td className="small">{c.relationship_manager?.name ?? '—'}</td>
                    <td className="r num">{money(c.lifetime_value, cur, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ))}
        </Card>
      </div>
      {adding && <NewClientModal canVip={canVip} onClose={() => setAdding(false)} onCreated={(id) => { setAdding(false); nav(`/clients/${id}`); }} />}
    </>
  );
}

function NewClientModal({ canVip, onClose, onCreated }: { canVip: boolean; onClose: () => void; onCreated: (id: number) => void }) {
  const { t, lang } = useT();
  const [f, setF] = useState<NewClient>({ name: '', tier: 'standard', lang: lang === 'ar' ? 'ar_001' : 'en_US' });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof NewClient, v: string | number | boolean) => setF({ ...f, [k]: v });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { const c = await api.createClient(f); onCreated(c.id); }
    catch (ex) { setErr((ex as Error).message); }
    finally { setBusy(false); }
  };
  return (
    <div className="modal" onClick={onClose}>
      <form className="card box" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <div className="bd" style={{ display: 'grid', gap: 10 }}>
          <h3>{t('new_client')}</h3>
          <label className="fld"><span>{t('name')}</span><input required value={f.name} onChange={(e) => set('name', e.target.value)} dir="auto" /></label>
          <div className="two">
            <label className="fld"><span>{t('phone')}</span><input value={f.phone ?? ''} onChange={(e) => set('phone', e.target.value)} /></label>
            <label className="fld"><span>{t('email')}</span><input type="email" value={f.email ?? ''} onChange={(e) => set('email', e.target.value)} /></label>
          </div>
          <div className="two">
            <label className="fld"><span>{t('city')}</span><input value={f.city ?? ''} onChange={(e) => set('city', e.target.value)} dir="auto" /></label>
            <label className="fld"><span>{t('language_pref')}</span>
              <select value={f.lang} onChange={(e) => set('lang', e.target.value)}><option value="en_US">English</option><option value="ar_001">العربية</option></select></label>
          </div>
          <div className="two">
            <label className="fld"><span>{t('tier')}</span>
              <select value={f.tier} onChange={(e) => set('tier', e.target.value)}>
                {['standard', 'preferred', ...(canVip ? ['private', 'royal'] : [])].map((k) => <option key={k} value={k}>{tierLabel(lang, k)}</option>)}
              </select>
              {!canVip && <small className="muted">{t('restricted_tiers_vip')}</small>}</label>
            <label className="fld"><span>{t('preferred_karats')}</span><input placeholder="22,21" value={f.preferred_karats ?? ''} onChange={(e) => set('preferred_karats', e.target.value)} /></label>
          </div>
          <div className="two">
            <label className="fld"><span>{t('typical_spend')}</span><input type="number" min="0" step="100" value={f.typical_budget ?? ''} onChange={(e) => set('typical_budget', Number(e.target.value))} /></label>
            <label className="fld chk"><input type="checkbox" checked={!!f.no_marketing} onChange={(e) => set('no_marketing', e.target.checked)} /> {t('no_marketing_label')}</label>
          </div>
          <label className="fld"><span>{t('taste_notes')}</span><textarea rows={2} value={f.taste_notes ?? ''} onChange={(e) => set('taste_notes', e.target.value)} dir="auto" /></label>
          {err && <div className="notice warn">{err}</div>}
          <div className="actions">
            <button className="btn" disabled={busy || !f.name.trim()}>{t('create')}</button>
            <button type="button" className="btn ghost" onClick={onClose}>{t('cancel')}</button>
          </div>
        </div>
      </form>
    </div>
  );
}
