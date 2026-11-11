import { useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { api, type Rate, type User } from '../lib/api';
import { useT } from '../lib/i18n';
import { grams, money } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, useLoad } from '../components/ui';

const KARATS = ['24', '22', '21', '18', '14', '9'];
const CATS = ['bangle', 'chain', 'necklace', 'ring', 'earrings', 'bracelet', 'pendant', 'set', 'coin'];
const PAGE = 25;
const GLYPH: Record<string, string> = { bangle: '◯', chain: '⌇', necklace: '◡', ring: '◎', earrings: '⫶', bracelet: '⊂', pendant: '◇', set: '❖', coin: '●' };

export default function Pieces() {
  const { t, lang } = useT();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const nav = useNavigate();
  const [q, setQ] = useState('');
  const [karat, setKarat] = useState('');
  const [onHand, setOnHand] = useState(true);
  const [cat, setCat] = useState('');
  const [sort, setSort] = useState('serial');
  const [page, setPage] = useState(0);
  const pieces = useLoad(() => api.pieces({ q, karat, on_hand: onHand, category: cat, sort, limit: PAGE, offset: page * PAGE }), [q, karat, onHand, cat, sort, page]);
  const total = pieces.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE));
  const cur = user.company.currency;

  return (
    <>
      <TopBar title={t('pieces_title')} sub={t('pieces_sub')} rate={rate} />
      <div className="content">
        <div className="toolbar">
          <input placeholder={t('search')} value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} aria-label={t('search')} />
          <select value={karat} onChange={(e) => { setKarat(e.target.value); setPage(0); }} aria-label={t('karat')}>
            <option value="">{t('karat')}: {t('all')}</option>
            {KARATS.map((k) => <option key={k} value={k}>{k}K</option>)}
          </select>
          <select value={cat} onChange={(e) => { setCat(e.target.value); setPage(0); }} aria-label={t('category')}>
            <option value="">{t('category')}: {t('all')}</option>
            {CATS.map((k) => <option key={k} value={k}>{t(`cat_${k}`)}</option>)}
          </select>
          <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(0); }} aria-label={t('sort')}>
            {['serial', 'price', 'price_asc', 'weight', 'recent'].map((k) => <option key={k} value={k}>{t('sort')}: {t(`sort_${k}`)}</option>)}
          </select>
          <label className="small"><input type="checkbox" checked={onHand} onChange={(e) => setOnHand(e.target.checked)} /> {t('on_hand')}</label>
          <span className="sp" />
          {pieces.data && <span className="small muted num">{total}</span>}
        </div>
        <Card title={t('pieces_title')} right={pages > 1 ? (
          <div className="pager">
            <button className="btn ghost small" disabled={page === 0} onClick={() => setPage(page - 1)}>{t('prev')}</button>
            <span className="small muted">{page + 1} {t('page_of')} {pages}</span>
            <button className="btn ghost small" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>{t('next_page')}</button>
          </div>) : undefined}>
          {pieces.error && <ErrorBox error={pieces.error} retry={pieces.reload} />}
          {pieces.loading ? <Loading /> : pieces.data && (pieces.data.items.length === 0 ? <Empty /> : (
            <table className="tbl">
              <thead><tr>
                <th>{t('serial')}</th><th>{t('product')}</th><th>{t('karat')}</th>
                <th className="r">{t('gross')}</th><th className="r">{t('net')}</th><th className="r">{t('stones')}</th>
                <th className="r">{t('price')}</th><th>{t('location')}</th><th>{t('rfid')}</th>
              </tr></thead>
              <tbody>
                {pieces.data.items.map((p) => (
                  <tr key={p.id} className="row" onClick={() => nav(`/pieces/${p.id}`)}>
                    <td><b>{p.serial}</b></td>
                    <td className="withthumb">{p.image_url ? <img className="thumb" src={p.image_url} alt="" loading="lazy" /> : <span className="glyph thumb" aria-hidden="true">{GLYPH[p.category ?? ''] ?? '◇'}</span>}<span>{p.product?.name}{p.category && <div className="small muted">{t(`cat_${p.category}`)}</div>}</span></td>
                    <td>{p.karat ? `${p.karat}K` : '—'}</td>
                    <td className="r num">{grams(p.gross_weight_g, lang)}</td>
                    <td className="r num">{grams(p.net_weight_g, lang)}</td>
                    <td className="r num">{money(p.stones_value, cur, lang)}</td>
                    <td className="r num"><b>{money(p.price_incl_vat, cur, lang)}</b></td>
                    <td>{p.on_hand > 0 ? <span className="tag good">{p.location?.name ?? t('on_hand')}</span> : <span className="tag warn">{t('out')}</span>}</td>
                    <td className="small muted">{p.rfid_tag ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ))}
        </Card>
      </div>
    </>
  );
}
