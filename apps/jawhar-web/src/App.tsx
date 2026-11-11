import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { api, ApiError, type Rate, type User } from './lib/api';
import { I18nContext, type Lang } from './lib/i18n';
import Shell from './components/Shell';
import Login from './pages/Login';
import Today from './pages/Today';
import Cards from './pages/Cards';
import Pieces from './pages/Pieces';
import PieceDetail from './pages/PieceDetail';
import Clients from './pages/Clients';
import ClientDetail from './pages/ClientDetail';
import Documents from './pages/Documents';
import OrderDetail from './pages/OrderDetail';
import NewQuote from './pages/NewQuote';
import Counter from './pages/Counter';
import Invoices from './pages/Invoices';
import InvoiceDetail from './pages/InvoiceDetail';
import Memos from './pages/Memos';
import Rates from './pages/Rates';
import OldGold from './pages/OldGold';

function readLang(): Lang {
  try { return (localStorage.getItem('jawhar_lang') as Lang) || 'en'; } catch { return 'en'; }
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(readLang);
  const [user, setUser] = useState<User | null | undefined>(undefined); // undefined = checking
  const [rate, setRate] = useState<Rate | null>(null);

  const setLang = (l: Lang) => { setLangState(l); try { localStorage.setItem('jawhar_lang', l); } catch { /* fine */ } };
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  }, [lang]);

  const loadRate = () => api.rateCurrent().then((r) => setRate(r.rate), () => setRate(null));
  useEffect(() => {
    api.me().then((u) => { setUser(u); loadRate(); }, (e) => {
      setUser(null);
      if (!(e instanceof ApiError && e.status === 401)) console.error(e);
    });
  }, []);

  const signOut = async () => { try { await api.logout(); } finally { setUser(null); } };

  return (
    <I18nContext.Provider value={{ lang, setLang }}>
      {user === undefined ? null : user === null ? (
        <Login onSignedIn={(u) => { setUser(u); loadRate(); }} />
      ) : (
        <Routes>
          <Route element={<Shell user={user} rate={rate} onSignOut={signOut} />}>
            <Route index element={<Today />} />
            <Route path="cards" element={<Cards />} />
            <Route path="pieces" element={<Pieces />} />
            <Route path="pieces/:id" element={<PieceDetail />} />
            <Route path="clients" element={<Clients />} />
            <Route path="clients/:id" element={<ClientDetail />} />
            <Route path="documents" element={<Documents />} />
            <Route path="counter" element={<Counter />} />
            <Route path="documents/new" element={<NewQuote />} />
            <Route path="documents/:id" element={<OrderDetail />} />
            <Route path="invoices" element={<Invoices />} />
            <Route path="invoices/:id" element={<InvoiceDetail />} />
            <Route path="memos" element={<Memos />} />
            <Route path="rates" element={<Rates />} />
            <Route path="old-gold" element={<OldGold />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      )}
    </I18nContext.Provider>
  );
}
