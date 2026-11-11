import { useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { api, type Rate, type User } from '../lib/api';
import { useT } from '../lib/i18n';
import { grams, money } from '../lib/format';
import { TopBar } from '../components/Shell';
import { Card, Empty, ErrorBox, Loading, useLoad } from '../components/ui';

const KARATS = ['24', '22', '21', '18', '14', '9'];

export default function Pieces() {
  const { t, lang } = useT();
  const { user, rate } = useOutletContext<{ user: User; rate: Rate | null }>();
  const nav = useNavigate();
  const [q, setQ] = useState('');
  const [karat, setKarat] = useState('');
  const [onHand, setOnHand] = useState(true);
  const pieces = useLoad(() => api.pieces({ q, karat, on_hand: onHand, limit: 100 }), [q, karat, onHand]);
  const cur = user.company.currency;

  return (
    <>
      <TopBar title={t('pieces_title')} sub={t('pieces_sub')} rate={rate} />
      <div className="content">
        <div className="toolbar">
          <input placeholder={t('search')} value={q} onChange={(e) => setQ(e.target.value)} aria-label={t('search')} />
          <select value={karat} onChange={(e) => setKarat(e.target.value)} aria-label={t('karat')}>
            <option value="">{t('karat')}: {t('all')}</option>
            {KARATS.map((k) => <option key={k} value={k}>{k}K</option>)}
          </select>
          <label className="small"><input type="checkbox" checked={onHand} onChange={(e) => setOnHand(e.target.checked)} /> {t('on_hand')}</label>
          <span className="sp" />
          {pieces.data && <span className="small muted num">{pieces.data.total}</span>}
        </div>
        <Card title={t('pieces_title')}>
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
                    <td>{p.product?.name}</td>
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
