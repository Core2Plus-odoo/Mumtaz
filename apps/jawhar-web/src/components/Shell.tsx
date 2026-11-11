import { NavLink, Outlet } from 'react-router-dom';
import type { Rate, User } from '../lib/api';
import { useT } from '../lib/i18n';
import { num, when } from '../lib/format';

const Icon = ({ d }: { d: string }) => <svg viewBox="0 0 24 24"><path d={d} /></svg>;
const ICONS = {
  today: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z',
  clients: 'M9 11a3 3 0 100-6 3 3 0 000 6zM3 20a6 6 0 0112 0M16 11a3 3 0 100-6M18 20a6 6 0 00-3-5.2',
  docs: 'M6 3h9l5 5v13H6zM14 3v6h6M9 13h6M9 17h6',
  invoices: 'M4 4h16v16H4zM8 9h8M8 13h8M8 17h4',
  pieces: 'M12 3l9 5v8l-9 5-9-5V8zM3.5 7.5L12 12l8.5-4.5M12 12v9',
  memos: 'M4 5h16v12H7l-3 3zM8 10h8M8 13h5',
  rates: 'M3 20h18M5 20V9l7-5 7 5v11M9 20v-6h6v6',
  oldgold: 'M12 3v18M7 8h7a3 3 0 010 6H8a3 3 0 000 6h9',
  cards: 'M4 8h16v11H4zM4 8l2-4h12l2 4M9 13h6',
  counter: 'M3 6h18v12H3zM3 10h18M7 14h4',
  pipeline: 'M4 19V5M4 19h16M8 15V9M12 15v-3M16 15V7',
};

export default function Shell({ user, rate, onSignOut }: { user: User; rate: Rate | null; onSignOut: () => void }) {
  const { t, lang, setLang } = useT();
  const nav = (to: string, icon: keyof typeof ICONS, label: string, end = false) => (
    <NavLink to={to} end={end} className={({ isActive }) => `navb ${isActive ? 'on' : ''}`}>
      <Icon d={ICONS[icon]} />{label}
    </NavLink>
  );
  return (
    <div className="shell">
      <nav className="rail">
        <div className="brandrow">
          <span className="mk">J</span>
          <span><b>{t('app')}</b><small>{user.company.name}</small></span>
        </div>
        <div className="railsec">{t('nav_today')}</div>
        {nav('/', 'today', t('nav_today'), true)}
        {nav('/cards', 'cards', t('nav_cards'))}
        <div className="railsec">{t('nav_sales')}</div>
        {nav('/counter', 'counter', t('nav_counter'))}
        {nav('/clients', 'clients', t('nav_clients'))}
        {nav('/pipeline', 'pipeline', t('nav_pipeline'))}
        {nav('/documents', 'docs', t('nav_documents'))}
        {nav('/invoices', 'invoices', t('nav_invoices'))}
        <div className="railsec">{t('nav_inventory')}</div>
        {nav('/pieces', 'pieces', t('nav_pieces'))}
        {nav('/memos', 'memos', t('nav_memos'))}
        <div className="railsec">{t('nav_finance')}</div>
        {nav('/rates', 'rates', t('nav_rates'))}
        {nav('/old-gold', 'oldgold', t('nav_old_gold'))}
        <div className="railfoot">
          <div>{user.name}<br /><span style={{ color: '#4B5A6C' }}>{user.roles.join(' · ') || '—'}</span></div>
          <button onClick={() => setLang(lang === 'en' ? 'ar' : 'en')}>{t('language')}</button>
          <button onClick={onSignOut}>{t('sign_out')}</button>
        </div>
      </nav>
      <div className="main">
        <div className="util">
          <span className="env">{t('prototype')}</span>
          <span>{t('app')}</span><span className="sep">/</span><span>{user.company.name}</span>
          <span className="sp" />
          <span>{t('engine')}</span>
          <span className="sep">·</span>
          {rate
            ? <span>{t('rate_approved')} {when(rate.approved_at ?? rate.effective_at, lang)} {rate.approved_by ? `· ${rate.approved_by.name}` : ''}</span>
            : <span>{t('rate_none')}</span>}
        </div>
        <Outlet context={{ user, rate }} />
      </div>
    </div>
  );
}

export function TopBar({ title, sub, rate, children }: { title: string; sub?: React.ReactNode; rate?: Rate | null; children?: React.ReactNode }) {
  const { t, lang } = useT();
  return (
    <div className="topbar">
      <div className="crumb">{sub}<b>{title}</b></div>
      <span className="sp" />
      {children}
      {rate !== undefined && (
        rate
          ? <div className="rate"><small>{t('rate_24k')}</small><b className="num">{num(rate.rate_per_gram, lang)} {rate.currency}/{t('unit_g')}</b></div>
          : <div className="rate none"><small>{t('rate_24k')}</small><b>{t('rate_none')}</b></div>
      )}
    </div>
  );
}
