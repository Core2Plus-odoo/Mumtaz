import { useState } from 'react';
import { Link, useOutletContext, useParams } from 'react-router-dom';
import { api, type Rate, type User } from '../lib/api';
import { useT } from '../lib/i18n';
import { grams, money, num, pct, when } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, ErrorBox, Loading, StateTag, useLoad } from '../components/ui';
import { stateLabel } from '../lib/i18n';

export default function PieceDetail() {
  const { id } = useParams();
  const { t, lang } = useT();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const [discount, setDiscount] = useState(0);
  const piece = useLoad(() => api.piece(Number(id), discount || undefined), [id, discount]);
  const cur = user.company.currency;
  const p = piece.data;
  const b = p?.breakdown;

  return (
    <>
      <TopBar title={p ? `${p.serial} · ${p.product?.name ?? ''}` : t('loading')} sub={<Link to="/pieces">← {t('pieces_title')}</Link> } rate={rate} />
      <div className="content">
        {piece.error && <ErrorBox error={piece.error} retry={piece.reload} />}
        {piece.loading && !p && <Loading />}
        {p && (
          <div className="two">
            <Card title={t('breakdown')} sub={t('breakdown_sub')}>
              {b ? (
                <div className="bk">
                  <div className="ln"><span>{t('rate_24k')}</span><span className="num">{num(b.rate_24k_per_g, lang)} {p.rate?.currency}/{t('unit_g')}</span></div>
                  <div className="ln"><span>{t('fine_weight')}</span><span className="num">{grams(b.fine_weight_g, lang)}</span></div>
                  <div className="ln"><span>{t('metal_value')}</span><span className="num">{money(b.metal_value, cur, lang)}</span></div>
                  <div className="ln"><span>{t('wastage_value')} ({pct(p.wastage_pct, lang)})</span><span className="num">{money(b.wastage_value, cur, lang)}</span></div>
                  <div className="ln"><span>{t('making_charge')}{discount ? ` · −${pct(discount, lang)}` : ''}</span><span className="num">{money(b.making_charge, cur, lang)}</span></div>
                  <div className="ln"><span>{t('stones_value')}</span><span className="num">{money(b.stones_value, cur, lang)}</span></div>
                  <div className="ln"><span>{t('subtotal')}</span><span className="num">{money(b.subtotal, cur, lang)}</span></div>
                  <div className="ln"><span>{t('vat')}</span><span className="num">{money(b.vat, cur, lang)}</span></div>
                  <div className="ln total"><span>{t('total')}</span><span className="num">{money(b.total, cur, lang)}</span></div>
                  <div className="toolbar" style={{ marginTop: 12 }}>
                    <label className="small">{t('dealer_discount')}
                      <select value={discount} onChange={(e) => setDiscount(Number(e.target.value))} style={{ marginInlineStart: 8, minWidth: 90 }}>
                        {[0, 5, 10, 15, 20].map((d) => <option key={d} value={d}>{d}%</option>)}
                      </select>
                    </label>
                    <span className="small muted">{t('discount_note')}</span>
                  </div>
                  {p.rate && <div className="small muted" style={{ marginTop: 8 }}>
                    {t('rate_approved')} {when(p.rate.approved_at ?? p.rate.effective_at, lang)} · {t('rate_by')} {p.rate.approved_by?.name ?? '—'}
                  </div>}
                </div>
              ) : <div className="err">{t('no_breakdown')}: {p.breakdown_unavailable}</div>}
            </Card>
            <Card title={p.serial}>
              <dl className="dl">
                <dt>{t('product')}</dt><dd>{p.product?.name}</dd>
                <dt>{t('karat')}</dt><dd>{p.karat ? `${p.karat}K` : '—'}</dd>
                <dt>{t('gross')}</dt><dd className="num">{grams(p.gross_weight_g, lang)}</dd>
                <dt>{t('stones')}</dt><dd className="num">{grams(p.stone_weight_g, lang)} · {money(p.stones_value, cur, lang)}</dd>
                <dt>{t('net')}</dt><dd className="num">{grams(p.net_weight_g, lang)}</dd>
                <dt>{t('wastage')}</dt><dd className="num">{pct(p.wastage_pct, lang)}</dd>
                <dt>{t('making')}</dt><dd className="num">{p.making_type === 'percent' ? pct(p.making_value, lang) : p.making_type === 'per_gram' ? `${money(p.making_value, cur, lang)}/${t('unit_g')}` : money(p.making_value, cur, lang)}</dd>
                <dt>{t('rfid')}</dt><dd>{p.rfid_tag ?? '—'}</dd>
                <dt>{t('certificate')}</dt><dd>{p.certificate_ref ?? '—'}</dd>
                <dt>{t('location')}</dt><dd>{p.on_hand > 0 ? <span className="tag good">{p.location?.name ?? t('on_hand')}</span> : <span className="tag warn">{t('out')}</span>}</dd>
              </dl>
              {p.memos.length > 0 && (
                <>
                  <h4 style={{ margin: '16px 0 8px' }}>{t('memos_title')}</h4>
                  <table className="tbl"><tbody>
                    {p.memos.map((m) => (
                      <tr key={m.id}><td><b>{m.name}</b></td><td>{m.client?.name}</td><td className="num">{when(m.return_by, lang, false)}</td><td><StateTag state={m.state} label={stateLabel(lang, m.state)} /></td></tr>
                    ))}
                  </tbody></table>
                </>
              )}
            </Card>
          </div>
        )}
      </div>
    </>
  );
}
