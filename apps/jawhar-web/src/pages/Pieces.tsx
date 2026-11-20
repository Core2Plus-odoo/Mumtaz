import { useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { api, type ImportResult, type Rate, type User } from '../lib/api';
import { useT } from '../lib/i18n';
import { grams, money, when } from '../lib/format';
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
  const isManager = user.roles.includes('jewellery_manager');
  const [importing, setImporting] = useState(false);

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
        {isManager && (
          <div className="actions" style={{ marginBottom: 12 }}>
            <button className="btn ghost small" onClick={() => setImporting(!importing)}>{importing ? t('import_hide') : t('import_pieces')}</button>
          </div>
        )}
        {isManager && importing && <ImportPanel onDone={() => { pieces.reload(); }} />}
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

/** The stock book as a spreadsheet: preview every row, then write the new
 * pieces onto the shelf. A serial already in the book is skipped, so a file
 * can be loaded twice; a row with a problem is named by line. */
function ImportPanel({ onDone }: { onDone: () => void }) {
  const { t, lang } = useT();
  const [csv, setCsv] = useState('');
  const [xlsx, setXlsx] = useState<string | null>(null);
  const [fileName, setFileName] = useState('');
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [skipErrors, setSkipErrors] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'warn'; text: string } | null>(null);
  const runs = useLoad(() => api.piecesImports());
  const payload = () => (xlsx ? { xlsx } : { csv });
  const pick = (f: File | undefined) => {
    setPreview(null); setMsg(null);
    if (!f) return;
    setFileName(f.name);
    const r = new FileReader();
    if (/\.xlsx$/i.test(f.name)) { r.onload = () => { setXlsx(String(r.result).split(',')[1] ?? null); setCsv(''); }; r.readAsDataURL(f); }
    else { r.onload = () => { setCsv(String(r.result)); setXlsx(null); }; r.readAsText(f); }
  };
  const run = async (dry: boolean) => {
    setBusy(true); setMsg(null);
    try {
      const out = await api.piecesImport({ ...payload(), dry_run: dry, skip_errors: skipErrors, name: fileName || undefined });
      setPreview(out);
      if (!dry) { setMsg({ kind: 'ok', text: `${t('import_done')}: ${out.summary.new} ${t('import_new')}, ${out.summary.exists} ${t('import_exists')}, ${out.summary.errors} ${t('import_errors')}` }); runs.reload(); onDone(); }
    } catch (e) { setMsg({ kind: 'warn', text: (e as Error).message }); }
    finally { setBusy(false); }
  };
  const template = async () => {
    const tpl = await api.piecesImportTemplate();
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([tpl.csv], { type: 'text/csv' })); a.download = 'pieces-import-template.csv'; a.click();
  };
  const ready = !!(csv.trim() || xlsx);
  return (
    <Card title={t('import_pieces')} sub={t('import_sub')}>
      <div className="kyc">
        <p className="small muted">{t('import_rule')} <a href="#" onClick={(e) => { e.preventDefault(); void template(); }}>{t('import_template')}</a></p>
        <div className="actions">
          <input type="file" accept=".csv,.txt,.xlsx" onChange={(e) => pick(e.target.files?.[0])} aria-label={t('import_file')} />
          <label className="small"><input type="checkbox" checked={skipErrors} onChange={(e) => setSkipErrors(e.target.checked)} /> {t('import_skip_errors')}</label>
        </div>
        <textarea className="payload" rows={4} placeholder={t('import_paste')} value={csv} onChange={(e) => { setCsv(e.target.value); setXlsx(null); setPreview(null); }} dir="ltr" />
        <div className="actions">
          <button className="btn ghost" disabled={busy || !ready} onClick={() => run(true)}>{t('import_preview')}</button>
          <button className="btn" disabled={busy || !ready || !preview || !preview.dry_run || (preview.summary.errors > 0 && !skipErrors) || preview.summary.new === 0} onClick={() => run(false)}>{t('import_apply')}</button>
        </div>
        {msg && <div className={`notice ${msg.kind}`}>{msg.text}</div>}
        {preview && (
          <>
            <div className="small"><b className="num">{preview.summary.rows}</b> {t('import_rows')} · <span className="tag ok">{preview.summary.new} {t('import_new')}</span> <span className="tag">{preview.summary.exists} {t('import_exists')}</span> <span className={`tag ${preview.summary.errors ? 'bad' : ''}`}>{preview.summary.errors} {t('import_errors')}</span></div>
            <table className="tbl">
              <thead><tr><th>#</th><th>{t('serial')}</th><th>{t('product')}</th><th>{t('state')}</th><th>{t('note')}</th></tr></thead>
              <tbody>{preview.rows.slice(0, 200).map((r) => (
                <tr key={r.line}><td className="num">{r.line}</td><td><b>{r.serial || '—'}</b></td><td>{r.design}</td>
                  <td><span className={`tag ${r.status === 'new' ? 'ok' : r.status === 'error' ? 'bad' : ''}`}>{t(`import_${r.status}`)}</span></td>
                  <td className="small muted">{r.message}</td></tr>))}</tbody>
            </table>
          </>
        )}
        {runs.data && runs.data.items.length > 0 && (
          <div><div className="small muted">{t('import_runs')}</div>
            <ul className="plain small">{runs.data.items.slice(0, 5).map((r) => <li key={r.id}>{r.name} · {r.by?.name} · {when(r.at, lang)} · {r.created} {t('import_new')} · {r.skipped} {t('import_exists')} · {r.errors} {t('import_errors')}</li>)}</ul></div>
        )}
      </div>
    </Card>
  );
}
