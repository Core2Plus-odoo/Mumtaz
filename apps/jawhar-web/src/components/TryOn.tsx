// Virtual try-on: the client's camera with the piece placed on her, all on
// the device, with a fit read off her body. Face, hand and body landmarks
// come from MediaPipe running in the browser from files the app serves
// itself; no frame leaves the kiosk. The iris (11.7 mm in every adult) is
// the ruler: from it the piece is drawn at its true size, a chain sits
// where its length puts it, and height, wrist, ring and bangle sizes are
// estimated for the fitter to confirm. A saved look is a picture on this
// screen only; what travels with a request is one line of estimates.
import { useEffect, useRef, useState } from 'react';
import { placeOnFace, placeOnHand, usesFace, usesHand, type Category, type Placement, type Pt } from '../lib/tryon';
import { chainFit, measureBody, measureFace, measureHand, scaleFromIris, summarise, type BodyMeasure, type Dims, type FaceMeasure, type FitSummary, type HandMeasure, type Scale, type Vis } from '../lib/fit';
import { useT } from '../lib/i18n';

const MP = '/app/mediapipe';
type Vision = typeof import('@mediapipe/tasks-vision');
type Tracker = { face?: Vision['FaceLandmarker']['prototype']; hand?: Vision['HandLandmarker']['prototype']; pose?: Vision['PoseLandmarker']['prototype'] };
export type Cues = { scale: boolean; body: boolean; hand: boolean; face: boolean };
type Look = { url: string; at: number };

const ema = (prev: number | undefined, next: number, a = 0.12) => (prev === undefined ? next : prev + (next - prev) * a);

export default function TryOn({ category, cutoutUrl, label, dims, onClose, onAskViewing, onFit }: {
  category: Category; cutoutUrl: string; label: string; dims?: Dims | null;
  onClose: () => void; onAskViewing?: (fit: FitSummary | null) => void; onFit?: (fit: FitSummary | null) => void;
}) {
  const { t, lang } = useT();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [state, setState] = useState<'starting' | 'tracking' | 'none' | 'frozen' | 'error'>('starting');
  const [err, setErr] = useState<string | null>(null);
  const [fit, setFit] = useState<FitSummary | null>(null);
  const [cues, setCues] = useState<Cues>({ scale: false, body: false, hand: false, face: false });
  const [looks, setLooks] = useState<Look[]>([]);
  const [viewing, setViewing] = useState<Look | null>(null);
  const [guides, setGuides] = useState(true);
  const frozen = useRef(false);
  const guidesRef = useRef(true);
  const fitRef = useRef<FitSummary | null>(null);
  guidesRef.current = guides;

  useEffect(() => {
    let stream: MediaStream | null = null;
    let raf = 0;
    let alive = true;
    const tracker: Tracker = {};
    const cutout = new Image();
    cutout.src = cutoutUrl;
    const run = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 960 }, height: { ideal: 1280 } }, audio: false });
        const video = videoRef.current!;
        video.srcObject = stream;
        await video.play();
        const vision = await import('@mediapipe/tasks-vision');
        const files = await vision.FilesetResolver.forVisionTasks(`${MP}/wasm`);
        // the face is always tracked: it is the ruler, even for a ring
        tracker.face = await vision.FaceLandmarker.createFromOptions(files, {
          baseOptions: { modelAssetPath: `${MP}/face_landmarker.task` }, runningMode: 'VIDEO', numFaces: 1 });
        if (usesHand(category)) {
          tracker.hand = await vision.HandLandmarker.createFromOptions(files, {
            baseOptions: { modelAssetPath: `${MP}/hand_landmarker.task` }, runningMode: 'VIDEO', numHands: 1 });
        }
        tracker.pose = await vision.PoseLandmarker.createFromOptions(files, {
          baseOptions: { modelAssetPath: `${MP}/pose_landmarker_lite.task` }, runningMode: 'VIDEO', numPoses: 1 });
        if (!alive) return;
        setState('tracking');
        const canvas = canvasRef.current!;
        const ctx = canvas.getContext('2d')!;
        let lastTs = -1;
        let seen = 0;
        let frame = 0;
        let lastPublish = 0;
        let face: Pt[] | null = null;
        let hand: Pt[] | null = null;
        let pose: Vis[] | null = null;
        let scale: Scale | null = null;
        let faceM: FaceMeasure | null = null;
        let handM: HandMeasure | null = null;
        let bodyM: BodyMeasure | null = null;
        const smooth: Partial<Record<'height' | 'neck' | 'wrist' | 'ring' | 'bangle' | 'shoulder', number>> = {};
        const draw = () => {
          if (!alive) return;
          raf = requestAnimationFrame(draw);
          if (frozen.current || video.readyState < 2) return;
          const w = video.videoWidth, h = video.videoHeight;
          if (!w || !h) return;
          if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
          const ts = performance.now();
          if (ts === lastTs) return;
          lastTs = ts; frame++;
          // -- track: the face every frame it places something, else every other; the hand every frame; the body every 4th
          if (tracker.face && (usesFace(category) || frame % 2 === 0)) {
            const r = tracker.face.detectForVideo(video, ts);
            face = r.faceLandmarks[0] ?? null;
            scale = face ? scaleFromIris(face, w, h) : null;
            faceM = face && scale ? measureFace(face, scale, w, h) : null;
          }
          if (tracker.hand) {
            const r = tracker.hand.detectForVideo(video, ts);
            hand = r.landmarks[0] ?? null;
          }
          if (tracker.pose && frame % 4 === 0) {
            const r = tracker.pose.detectForVideo(video, ts);
            pose = (r.landmarks[0] as Vis[] | undefined) ?? null;
          }
          // -- measure, smoothed so the numbers settle rather than flicker
          if (scale) {
            if (faceM) smooth.neck = ema(smooth.neck, faceM.neckGirthMm);
            handM = hand ? measureHand(hand, scale, w, h) : null;
            if (handM) { smooth.wrist = ema(smooth.wrist, handM.wristGirthMm); smooth.ring = ema(smooth.ring, handM.ringGirthMm); smooth.bangle = ema(smooth.bangle, handM.bangleDiameterMm); }
            bodyM = pose ? measureBody(pose, scale, w, h) : null;
            if (bodyM) { smooth.height = ema(smooth.height, bodyM.heightCm); smooth.shoulder = ema(smooth.shoulder, bodyM.shoulderWidthMm); }
          } else { handM = null; bodyM = null; }
          const faceS: FaceMeasure | null = faceM && smooth.neck ? { ...faceM, neckGirthMm: smooth.neck } : null;
          const handS: HandMeasure | null = handM && smooth.wrist && smooth.ring && smooth.bangle ? { ...handM, wristGirthMm: smooth.wrist, ringGirthMm: smooth.ring, bangleDiameterMm: smooth.bangle } : null;
          const bodyS: BodyMeasure | null = bodyM && smooth.height ? { ...bodyM, heightCm: Math.round(smooth.height) } : null;
          // -- place
          const aspect = cutout.naturalWidth && cutout.naturalHeight ? cutout.naturalWidth / cutout.naturalHeight : 1;
          let placements: Placement[] = [];
          if (usesFace(category) && face) placements = placeOnFace(face, category, aspect);
          else if (usesHand(category) && hand) placements = placeOnHand(hand, category, aspect);
          if (placements.length && scale && dims?.width_mm) {
            // true size: the cutout's real width in this frame, kept within reason of the landmark guess
            const trueW = dims.width_mm / scale.mmPerPx / w;
            placements = placements.map((p) => {
              const nw = Math.min(p.w * 1.8, Math.max(p.w * 0.55, trueW));
              return { ...p, w: nw, h: nw / aspect };
            });
          }
          if (placements.length === 1 && faceS && scale && dims?.length_mm && ['chain', 'necklace', 'set', 'pendant'].includes(category)) {
            // drape: a chain of this length sits this far below the neck base on this neck
            const drop = chainFit(dims.length_mm, faceS.neckGirthMm).dropMm / scale.mmPerPx / h;
            const p = placements[0];
            const y = category === 'pendant' ? faceS.neckBase.y + drop + p.h * 0.4 : faceS.neckBase.y + Math.max(drop * 0.5, p.h * 0.45);
            // when the frame ends above where it would sit (a close camera), keep it on the screen rather than lose it
            placements = [{ ...p, x: faceS.neckBase.x, y: Math.min(y, 1 - p.h * 0.55) }];
          }
          canvas.dataset.placed = String(placements.length);
          seen = placements.length ? Math.min(seen + 1, 10) : Math.max(seen - 1, 0);
          // -- draw, mirrored like a mirror
          ctx.save();
          ctx.translate(w, 0); ctx.scale(-1, 1);
          ctx.drawImage(video, 0, 0, w, h);
          for (const p of placements) {
            ctx.save();
            ctx.translate(p.x * w, p.y * h);
            ctx.rotate(p.angle);
            ctx.shadowColor = 'rgba(0,0,0,0.38)'; ctx.shadowBlur = Math.max(4, p.w * w * 0.06); ctx.shadowOffsetY = Math.max(2, p.h * h * 0.04);
            ctx.drawImage(cutout, -p.w * w / 2, -p.h * h / 2, p.w * w, p.h * h);
            ctx.restore();
          }
          ctx.restore();
          if (guidesRef.current && bodyS?.shoulders) {
            // a thin shoulder line with the height estimate, drawn unmirrored so the text reads
            const [a, b] = bodyS.shoulders;
            const ax = (1 - a.x) * w, bx = (1 - b.x) * w, ay = a.y * h, by = b.y * h;
            ctx.save();
            ctx.strokeStyle = 'rgba(214,176,96,0.9)'; ctx.lineWidth = Math.max(2, w / 400); ctx.setLineDash([w / 80, w / 120]);
            ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
            const tag = `≈ ${bodyS.heightCm} cm`;
            ctx.font = `600 ${Math.round(w / 28)}px system-ui, sans-serif`;
            const tw = ctx.measureText(tag).width + w / 40, th = w / 20;
            const cx = (ax + bx) / 2, cy = Math.min(ay, by) - th * 0.9;
            ctx.setLineDash([]); ctx.fillStyle = 'rgba(15,110,107,0.85)';
            ctx.beginPath(); ctx.roundRect(cx - tw / 2, cy - th / 2, tw, th, th / 2); ctx.fill();
            ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(tag, cx, cy);
            ctx.restore();
          }
          // -- publish, a few times a second
          if (ts - lastPublish > 400) {
            lastPublish = ts;
            const summary = scale ? summarise(bodyS, faceS, handS, dims ?? null, category) : null;
            const out = summary && Object.keys(summary).length ? summary : null;
            fitRef.current = out; setFit(out); onFit?.(out);
            setCues({ scale: !!scale, body: !!bodyS, hand: !!handS, face: !!face });
            setState((s) => (s === 'frozen' ? s : seen > 0 ? 'tracking' : 'none'));
          }
        };
        draw();
      } catch (e) {
        if (!alive) return;
        setErr(/NotAllowed|Permission|denied/i.test(String(e)) ? t('tryon_camera_denied') : String(e));
        setState('error');
      }
    };
    void run();
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      stream?.getTracks().forEach((tr) => tr.stop());
      tracker.face?.close(); tracker.hand?.close(); tracker.pose?.close();
      onFit?.(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, cutoutUrl]);

  const freeze = () => { frozen.current = !frozen.current; setState(frozen.current ? 'frozen' : 'tracking'); };
  const saveLook = () => {
    const c = canvasRef.current; if (!c || !c.width) return;
    try { const url = c.toDataURL('image/jpeg', 0.85); setLooks((ls) => [{ url, at: Date.now() }, ...ls].slice(0, 3)); } catch { /* a tainted canvas cannot be read; the look is simply not kept */ }
  };
  const hint = state === 'none' ? (usesFace(category) ? t('tryon_hint_face') : t('tryon_hint_hand')) : null;
  const cue = !cues.scale ? t('fit_measuring') : usesHand(category) && !cues.hand ? t('fit_hand') : !cues.body ? t('fit_shoulders') : null;
  const sits = fit?.chain_sits ? t(`sits_${fit.chain_sits}`) : null;
  const mm = (v: number) => `${lang === 'ar' ? v.toLocaleString('ar-EG') : v} ${t('mm')}`;

  return (
    <div className="tryon" role="dialog" aria-label={t('tryon_title')}>
      <div className="tryon-head">
        <b>{t('tryon_title')} · {label}</b>
        <span className="sp" />
        <button className="k2-btn ghost small" onClick={() => setGuides(!guides)} aria-pressed={guides}>{guides ? t('tryon_guides_off') : t('tryon_guides_on')}</button>
        <button className="k2-btn ghost" onClick={onClose}>{t('tryon_close')}</button>
      </div>
      <div className="tryon-body">
        <div className="tryon-stage">
          <video ref={videoRef} playsInline muted style={{ display: 'none' }} />
          <canvas ref={canvasRef} className="tryon-canvas" />
          {viewing && <img className="tryon-look-big" src={viewing.url} alt="" onClick={() => setViewing(null)} />}
          <div className={`tryon-state ${state}`}>
            {state === 'starting' && t('tryon_starting')}
            {state === 'none' && hint}
            {state === 'tracking' && (cue ?? t('tryon_tracking'))}
            {state === 'frozen' && t('tryon_frozen')}
            {state === 'error' && (err ?? t('error'))}
          </div>
        </div>
        <aside className="tryon-fit" aria-live="polite">
          <h3>{t('fit_title')}</h3>
          {dims && (dims.length_mm || dims.inner_diameter_mm) && (
            <div className="fit-piece small">{dims.length_mm ? `${t('fit_length')}: ${lang === 'ar' ? (dims.length_mm / 10).toLocaleString('ar-EG') : dims.length_mm / 10} ${t('cm')}` : ''}{dims.inner_diameter_mm ? `${t('fit_inner')}: ${mm(dims.inner_diameter_mm)}` : ''}</div>
          )}
          {!fit ? <p className="muted small">{cue ?? t('fit_measuring')}</p> : (
            <dl className="fit-list">
              {fit.height_cm && <><dt>{t('fit_height')}</dt><dd><b className="num">≈ {lang === 'ar' ? fit.height_cm.toLocaleString('ar-EG') : fit.height_cm} {t('cm')}</b> <span className="muted small">{fit.height_method === 'full_body' ? t('fit_full_body') : t('fit_from_shoulders')}</span></dd></>}
              {fit.neck_girth_mm && <><dt>{t('fit_neck')}</dt><dd className="num">≈ {mm(fit.neck_girth_mm)}{sits && <div className="small">{t('fit_chain_sits')} {sits}</div>}</dd></>}
              {fit.wrist_girth_mm && <><dt>{t('fit_wrist')}</dt><dd className="num">≈ {mm(fit.wrist_girth_mm)}</dd></>}
              {fit.bangle && <><dt>{t('fit_bangle')}</dt><dd className="num">{fit.bangle}</dd></>}
              {fit.ring_eu && <><dt>{t('fit_ring')}</dt><dd className="num">EU {fit.ring_eu} · US {fit.ring_us}</dd></>}
              {fit.verdict && <><dt>{t('fit_this_piece')}</dt><dd><span className={`tag ${fit.verdict === 'fits' ? 'ok' : 'warn'}`}>{t(`fit_${fit.verdict}`)}</span></dd></>}
            </dl>
          )}
          <p className="small muted">{t('fit_note')}</p>
          {looks.length > 0 && (
            <div className="tryon-looks">
              <div className="small muted">{t('tryon_looks')}</div>
              <div className="tryon-strip">{looks.map((l) => <img key={l.at} src={l.url} alt="" className={viewing?.at === l.at ? 'on' : ''} onClick={() => setViewing(viewing?.at === l.at ? null : l)} />)}</div>
            </div>
          )}
        </aside>
      </div>
      <div className="tryon-foot">
        <div className="actions">
          <button className="k2-btn" disabled={state === 'starting' || state === 'error'} onClick={freeze}>{state === 'frozen' ? t('tryon_resume') : t('tryon_snap')}</button>
          <button className="k2-btn ghost" disabled={state === 'starting' || state === 'error'} onClick={saveLook}>{t('tryon_save_look')}</button>
          {onAskViewing && <button className="k2-btn gold" onClick={() => onAskViewing(fitRef.current)}>{t('kiosk_ask_viewing')}</button>}
        </div>
        <p className="small muted">{t('tryon_privacy')}{fit ? ` ${t('tryon_fit_included')}` : ''}</p>
      </div>
    </div>
  );
}
