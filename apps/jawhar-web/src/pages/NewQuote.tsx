import { useState } from 'react';
import { Link, useNavigate, useOutletContext } from 'react-router-dom';
import { api, ApiError, type Client, type Piece, type Rate, type User } from '../lib/api';
import { tierLabel, useT } from '../lib/i18n';
import { grams, money } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, TierTag, useLoad } from '../components/ui';

/** Level D: a person builds the quotation; the engine prices every line. */
export default function NewQuote() {
  const { t, lang } = useT();
  const nav = useNavigate();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const cur = user.company.currency;
  const [clientQ, setClientQ] = useState('');
  const [client, setClient] = useState<Client | null>(null);
  const [pieceQ, setPieceQ] = useState('');
  const [picked, setPicked] = useState<{ piece: Piece; discount: number }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const clients = useLoad(() => api.clients({ q: clientQ, limit: 8 }), [clientQ]);
  const pieces = useLoad(() => api.pieces({ q: pieceQ, on_hand: true, limit: 12 }), [pieceQ]);

  const submit = async () => {
    if (!client) return;
    if (!picked.length) { setError(new Error(t('no_pieces_selected'))); return; }
    setBusy(true); setError(null);
    try {
      const order = await api.createQuote(client.id, picked.map((p) => ({ piece_id: p.piece.id, discount: p.discount })));
      nav(`/documents/${order.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e : (e as Error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <TopBar title={t('new_quote')} sub={<Link to="/documents">← {t('documents_title')}</Link>} rate={rate} />
      <div className="content">
        {!rate && <div className="err">{t('rate_none')}</div>}
        <div className="two">
          <div style={{ display: 'grid', gap: 18 }}>
            <Card title={t('pick_client')} right={client && <span><b>{client.name}</b> <TierTag tier={client.tier} label={tierLabel(lang, client.tier)} /></span>}>
              <div className="toolbar" style={{ marginBottom: 10 }}>
                <input placeholder={t('search')} value={clientQ} onChange={(e) => setClientQ(e.target.value)} aria-label={t('pick_client')} />
              </div>
              {clients.error && <ErrorBox error={clients.error} retry={clients.reload} />}
              {clients.loading ? <Loading /> : clients.data && (clients.data.items.length === 0 ? <Empty /> : (
                <table className="tbl"><tbody>
                  {clients.data.items.map((c) => (
                    <tr key={c.id} className="row" onClick={() => setClient(c)} aria-selected={client?.id === c.id}>
                      <td><b>{c.name}</b></td><td><TierTag tier={c.tier} label={tierLabel(lang, c.tier)} /></td>
                      <td className="r num">{money(c.lifetime_value, cur, lang)}</td>
                    </tr>))}
                </tbody></table>
              ))}
            </Card>
            <Card title={t('pick_pieces')}>
              <div className="toolbar" style={{ marginBottom: 10 }}>
                <input placeholder={t('search')} value={pieceQ} onChange={(e) => setPieceQ(e.target.value)} aria-label={t('pick_pieces')} />
              </div>
              {pieces.error && <ErrorBox error={pieces.error} retry={pieces.reload} />}
              {pieces.loading ? <Loading /> : pieces.data && (pieces.data.items.length === 0 ? <Empty /> : (
                <table className="tbl"><tbody>
                  {pieces.data.items.filter((p) => !picked.some((x) => x.piece.id === p.id)).map((p) => (
                    <tr key={p.id}>
                      <td><b>{p.serial}</b><div className="small muted">{p.product?.name}</div></td>
                      <td>{p.karat ? `${p.karat}K` : '—'}</td>
                      <td className="num">{grams(p.net_weight_g, lang)}</td>
                      <td className="r num">{money(p.price_incl_vat, cur, lang)}</td>
                      <td className="r"><button className="btn ghost" onClick={() => setPicked([...picked, { piece: p, discount: 0 }])}>{t('add_piece')}</button></td>
                    </tr>))}
                </tbody></table>
              ))}
            </Card>
          </div>
          <Card title={t('new_quote')} sub={t('new_quote_sub')}>
            {picked.length === 0 ? <Empty text={t('no_pieces_selected')} /> : (
              <table className="tbl">
                <thead><tr><th>{t('serial')}</th><th className="r">{t('price')}</th><th className="r">{t('dealer_discount')}</th><th /></tr></thead>
                <tbody>{picked.map((x, i) => (
                  <tr key={x.piece.id}>
                    <td><b>{x.piece.serial}</b><div className="small muted">{x.piece.product?.name}</div></td>
                    <td className="r num">{money(x.piece.price_incl_vat, cur, lang)}</td>
                    <td className="r">
                      <select value={x.discount} aria-label={t('dealer_discount')}
                        onChange={(e) => setPicked(picked.map((y, j) => (j === i ? { ...y, discount: Number(e.target.value) } : y)))}>
                        {[0, 5, 10, 15, 20].map((d) => <option key={d} value={d}>{d}%</option>)}
                      </select>
                    </td>
                    <td className="r"><button className="btn ghost" onClick={() => setPicked(picked.filter((_, j) => j !== i))}>{t('remove')}</button></td>
                  </tr>))}</tbody>
              </table>
            )}
            <p className="small muted">{t('discount_note')}</p>
            {error && <ErrorBox error={error} />}
            <button className="btn" style={{ marginTop: 12 }} disabled={busy || !client || !picked.length || !rate} onClick={submit}>
              {busy ? t('creating') : t('create_quote')}
            </button>
            {!client && <div className="small muted" style={{ marginTop: 8 }}>{t('pick_client')} →</div>}
          </Card>
        </div>
      </div>
    </>
  );
}
