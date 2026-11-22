import { useState, type FormEvent } from 'react';
import { api, ApiError, type User } from '../lib/api';
import { useT } from '../lib/i18n';

export default function Login({ onSignedIn }: { onSignedIn: (u: User) => void }) {
  const { t, lang, setLang } = useT();
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      onSignedIn(await api.login(login, password));
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t('wrong_credentials') : (err as Error).message || t('error'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login">
      <form className="box" onSubmit={submit}>
        <div className="brandrow">
          <span className="mk">J</span>
          <span><b>{t('app')}</b><small>{t('tagline')}</small></span>
        </div>
        <label htmlFor="login">{t('login')}</label>
        <input id="login" name="login" autoComplete="username" value={login} onChange={(e) => setLogin(e.target.value)} required autoFocus />
        <label htmlFor="password">{t('password')}</label>
        <input id="password" name="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <div className="err" role="alert" style={{ marginTop: 14 }}>{error}</div>}
        <button className="btn" type="submit" disabled={busy}>{busy ? t('signing_in') : t('sign_in')}</button>
        <div className="foot">
          <span>{t('engine')}</span>
          <a href="#" onClick={(e) => { e.preventDefault(); setLang(lang === 'en' ? 'ar' : 'en'); }}>{t('language')}</a>
        </div>
      </form>
    </div>
  );
}
