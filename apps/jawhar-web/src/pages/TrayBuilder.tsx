import { useState } from 'react';
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { api, ApiError, type Rate, type Tray, type User } from '../lib/api';
import { useT } from '../lib/i18n';
import { grams, money, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, useLoad } from '../components/ui';

/** Plan v3 wireframe 25: a small, diverse selection from available stock;
 *  staff keep control of suitability and sharing. */
export default function TrayBuilder() {
  const { id } = useParams();
  const { t, lang } = useT();
  const nav = useNavigate();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const cur = user.company.currency;
  const loaded = useLoad(() => api.tray(Number(id)), [id]);
  const [local, setLocal] = useState<Tray | null>(null);
  const [intent, setIntent] = useState<string | null>(null);
  const [budget, setBudget] = useState<string | null>(null);
  const [pieceQ, setPieceQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [link, setLink] = useState<{ url: string; expires: string | null } | null>(null);
  const [copied, setCopied] = useState(false);
  const pieces = useLoad(() => (pieceQ ? api.pieces({ q: pieceQ, on_hand: true, limit: 8 }) : Promise.resolve({ items: [] })), [pieceQ]);
  const tray = local ?? loaded.data;
  const editable = !!tray && (tray.state === 'draft' || tray.state === 'shared');

  const run = async (fn: () => Promise<Tray>) => {
    setBusy(true); setError(null);
    try { setLocal(await fn()); } catch (e) { setError(e instanceof ApiError ? e : (e as Error)); } finally { setBusy(false); }
  };
  const build = () => run(() => api.buildTray(tray!.id, {
    intent: intent ?? tray!.intent ?? undefined, budget: budget !== null ? Number(budget) : undefined, limit: 3 }));
  const share = async () => {
    setBusy(true); setError(null);
    try { const out = await api.shareTray(tray!.id); setLocal(out.tray); setLink({ url: out.url, expires: out.tray.link_expires }); }
    catch (e) { setError(e instanceof ApiError ? e : (e as Error)); } finally { setBusy(false); }
  };
  const reserve = async (pieceId: number) => {
    setBusy(true); setError(null);
    try { const out = await api.reserveTray(tray!.id, pieceId); setLocal(out.tray); nav(`/documents/${out.order.id}`); }
    catch (e) { setError(e instanceof ApiError ? e : (e as Error)); } finally { setBusy(false); }
  };
  const copy = async () => { if (link) { try { await navigator.clipboard.writeText(link.url); setCopied(true); } catch { /* shown anyway */ } } };

  return (
    <>
      <TopBar title={tray ? `${tray.name} · ${tray.client?.name ?? ''}` : t('loading')} sub={<Link to="/pipeline">← {t('pipeline_title')}</Link>} rate={rate}>
        {tray && <span className={`tag ${tray.state === 'won' ? 'good' : tray.state === 'closed' ? '' : 'teal'}`}>{t(`tray_state_${tray.state}`)}</span>}
      </TopBar>
      <div className="content">
        {loaded.error && <ErrorBox error={loaded.error} retry={loaded.reload} />}
        {loaded.loading && !tray && <Loading />}
        {tray && (
          <div className="two">
            <div style={{ display: 'grid', gap: 18 }}>
              <Card title={t('tray_title')} sub={t('tray_sub')}
                right={<span className="num"><b>{money(tray.total, cur, lang)}</b> · {tray.piece_count}</span>}>
                {editable && (
                  <div className="toolbar" style={{ marginBottom: 12 }}>
                    <input placeholder={t('tray_intent')} value={intent ?? tray.intent ?? ''} onChange={(e) => setIntent(e.target.value)} aria-label={t('tray_intent')} style={{ minWidth: 200 }} />
                    <input type="number" placeholder={t('tray_budget')} value={budget ?? (tray.budget || '')} onChange={(e) => setBudget(e.target.value)} aria-label={t('tray_budget')} style={{ minWidth: 160 }} />
                    {tray.restricted
                      ? <span className="small muted">{t('tray_manual')}</span>
                      : <button className="btn ghost" disabled={busy} onClick={build}>{tray.lines && tray.lines.length ? t('tray_rebuild') : t('tray_build')}</button>}
                  </div>
                )}
                {!tray.lines || tray.lines.length === 0 ? <Empty /> : (
                  <table className="tbl">
                    <thead><tr><th>#</th><th>{t('serial')}</th><th>{t('why')}</th><th className="r">{t('price')}</th><th /></tr></thead>
                    <tbody>{tray.lines.map((l) => (
                      <tr key={l.id} className={l.available ? '' : 'muted'}>
                        <td className="num">{l.sequence}</td>
                        <td><b>{l.piece.serial}</b><div className="small muted">{l.piece.product?.name} · {l.piece.karat ? `${l.piece.karat}K` : ''} · {grams(l.piece.net_weight_g, lang)}</div>
                          {l.feedback !== 'none' && <span className={`tag ${l.feedback === 'like' ? 'good' : 'bad'}`}>{l.feedback === 'like' ? t('liked') : t('not_for_her')}</span>}
                          {l.question && <div className="small" style={{ color: 'var(--gold-dark)' }}>{t('asked')}: {l.question}</div>}
                        </td>
                        <td className="small">{l.reasons.map((r, i) => <div key={i}>· {r}</div>)}{!l.available && <span className="tag bad">{t('out_of_stock')}</span>}</td>
                        <td className="r num">{money(l.price, cur, lang)}</td>
                        <td className="r">
                          {editable && <button className="btn ghost" disabled={busy} onClick={() => run(() => api.trayPiece(tray.id, l.piece.id, true))}>{t('replace')}</button>}
                          {(tray.state === 'shared' || tray.state === 'viewing' || tray.state === 'draft') && l.available && (
                            <button className="btn" style={{ marginInlineStart: 6 }} disabled={busy} onClick={() => reserve(l.piece.id)}>{t('reserve_piece')}</button>
                          )}
                        </td>
                      </tr>))}</tbody>
                  </table>
                )}
                {editable && (
                  <div className="toolbar" style={{ marginTop: 12 }}>
                    <input placeholder={t('search')} value={pieceQ} onChange={(e) => setPieceQ(e.target.value)} aria-label={t('pick_pieces')} />
                  </div>
                )}
                {editable && pieces.data && pieces.data.items.length > 0 && (
                  <table className="tbl" style={{ marginTop: 6 }}><tbody>{pieces.data.items.filter((p) => !tray.lines?.some((l) => l.piece.id === p.id)).map((p) => (
                    <tr key={p.id}><td><b>{p.serial}</b> <span className="small muted">{p.product?.name}</span></td><td className="r num">{money(p.price_incl_vat, cur, lang)}</td>
                      <td className="r"><button className="btn ghost" disabled={busy} onClick={() => run(() => api.trayPiece(tray.id, p.id))}>{t('add_to_tray')}</button></td></tr>))}</tbody></table>
                )}
                {error && <div style={{ marginTop: 12 }}><ErrorBox error={error} /></div>}
              </Card>
            </div>
            <div style={{ display: 'grid', gap: 18 }}>
              <Card title={t('share_link')}>
                {link && (
                  <div className="bk" style={{ marginBottom: 10 }}>
                    <div className="small">{t('link_ready')} {when(link.expires, lang)}</div>
                    <div className="toolbar"><input readOnly value={link.url} style={{ flex: 1, minWidth: 0 }} aria-label="link" /><button className="btn ghost" onClick={copy}>{copied ? t('copied') : t('copy')}</button></div>
                  </div>
                )}
                <dl className="dl">
                  <dt>{t('state')}</dt><dd>{t(`tray_state_${tray.state}`)}</dd>
                  <dt>{t('link_live')}</dt><dd>{tray.link_live ? when(tray.link_expires, lang) : (tray.link_expires ? t('link_revoked') : '—')}</dd>
                  <dt>{t('link_opened')}</dt><dd>{tray.link_opened_at ? when(tray.link_opened_at, lang) : '—'}</dd>
                  <dt>{t('viewing_requested')}</dt><dd>{tray.viewing_requested_at ? `${when(tray.viewing_requested_at, lang)} · ${tray.viewing_preferred ?? ''} ${tray.viewing_note ? '· ' + tray.viewing_note : ''}` : '—'}</dd>
                  <dt>{t('reserved_on')}</dt><dd>{tray.reservation ? <Link to={`/documents/${tray.reservation.id}`}>{tray.reservation.name}</Link> : '—'}</dd>
                </dl>
                <div className="toolbar" style={{ marginTop: 12 }}>
                  {editable && !tray.link_live && <button className="btn" disabled={busy || !tray.piece_count} onClick={share}>{t('share_link')}</button>}
                  {tray.link_live && <button className="btn ghost" disabled={busy} onClick={() => { setLink(null); run(() => api.revokeTray(tray.id)); }}>{t('revoke_link')}</button>}
                  {tray.state !== 'closed' && tray.state !== 'won' && <button className="btn ghost" disabled={busy} onClick={() => run(() => api.closeTray(tray.id))}>{t('close_tray')}</button>}
                </div>
                <p className="small muted" style={{ marginTop: 10 }}>{t('pub_request_note')}</p>
              </Card>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
