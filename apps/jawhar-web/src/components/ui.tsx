import { useEffect, useState, type ReactNode } from 'react';
import { ApiError } from '../lib/api';
import { useT } from '../lib/i18n';

/** Load something from the API once (and again when `deps` change). */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [state, set] = useState<{ data?: T; error?: ApiError | Error; loading: boolean }>({ loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    set((s) => ({ ...s, loading: true, error: undefined }));
    fn().then(
      (data) => alive && set({ data, loading: false }),
      (error) => alive && set({ error, loading: false }),
    );
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((n) => n + 1) };
}

export function Loading() {
  const { t } = useT();
  return <div className="empty">{t('loading')}</div>;
}

export function Empty({ text }: { text?: string }) {
  const { t } = useT();
  return <div className="empty">{text ?? t('empty')}</div>;
}

export function ErrorBox({ error, retry }: { error: Error; retry?: () => void }) {
  const { t } = useT();
  return (
    <div className="err" role="alert">
      <span>{error.message || t('error')}</span>
      {retry && <button className="btn ghost" onClick={retry}>{t('retry')}</button>}
    </div>
  );
}

export function Card({ title, sub, right, children }: { title: string; sub?: string; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      <div className="hd">
        <div><h3>{title}</h3>{sub && <div className="sub">{sub}</div>}</div>
        <span className="sp" />
        {right}
      </div>
      <div className="bd">{children}</div>
    </section>
  );
}

const TONE: Record<string, string> = {
  sale: 'good', posted: 'good', approved: 'good', paid: 'good', confirmed: 'good', returned: 'good',
  draft: '', sent: 'teal', to_approve: 'warn', partial: 'warn', out: 'warn', not_paid: 'bad',
  cancel: 'bad', cancelled: 'bad', rejected: 'bad', sold: 'gold', issued: 'gold', in_payment: 'teal',
};
export function StateTag({ state, label }: { state: string | false | null | undefined; label: string }) {
  return <span className={`tag ${state ? TONE[state] ?? '' : ''}`}>{label}</span>;
}

export function TierTag({ tier, label }: { tier: string | false | null | undefined; label: string }) {
  const tone = tier === 'royal' ? 'gold' : tier === 'private' ? 'teal' : tier === 'preferred' ? 'good' : '';
  return <span className={`tag ${tone}`}>{label}</span>;
}

export function Kpi({ label, value, sub, na }: { label: string; value: ReactNode; sub?: ReactNode; na?: boolean }) {
  return (
    <div className={`kpi ${na ? 'na' : ''}`}>
      <small>{label}</small>
      <b className="num">{value}</b>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}
