// Virtual try-on: the client's camera with the piece placed on her, all on
// the device. Face and hand landmarks come from MediaPipe running in the
// browser from files the app serves itself; no frame leaves the kiosk, and
// a snapshot is only ever drawn on the screen.
import { useEffect, useRef, useState } from 'react';
import { placeOnFace, placeOnHand, usesFace, usesHand, type Category, type Placement } from '../lib/tryon';
import { useT } from '../lib/i18n';

const MP = '/app/mediapipe';
type Tracker = { face?: import('@mediapipe/tasks-vision').FaceLandmarker; hand?: import('@mediapipe/tasks-vision').HandLandmarker };

export default function TryOn({ category, cutoutUrl, label, onClose, onAskViewing }: {
  category: Category; cutoutUrl: string; label: string; onClose: () => void; onAskViewing?: () => void;
}) {
  const { t } = useT();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [state, setState] = useState<'starting' | 'tracking' | 'none' | 'frozen' | 'error'>('starting');
  const [err, setErr] = useState<string | null>(null);
  const frozen = useRef(false);

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
        if (usesFace(category)) {
          tracker.face = await vision.FaceLandmarker.createFromOptions(files, {
            baseOptions: { modelAssetPath: `${MP}/face_landmarker.task` }, runningMode: 'VIDEO', numFaces: 1 });
        } else if (usesHand(category)) {
          tracker.hand = await vision.HandLandmarker.createFromOptions(files, {
            baseOptions: { modelAssetPath: `${MP}/hand_landmarker.task` }, runningMode: 'VIDEO', numHands: 1 });
        }
        if (!alive) return;
        setState('tracking');
        const canvas = canvasRef.current!;
        const ctx = canvas.getContext('2d')!;
        let lastTs = -1;
        let seen = 0;
        const draw = () => {
          if (!alive) return;
          raf = requestAnimationFrame(draw);
          if (frozen.current || video.readyState < 2) return;
          const w = video.videoWidth, h = video.videoHeight;
          if (!w || !h) return;
          if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
          ctx.save();
          ctx.translate(w, 0); ctx.scale(-1, 1);           // mirror, like a mirror
          ctx.drawImage(video, 0, 0, w, h);
          const ts = performance.now();
          if (ts === lastTs) { ctx.restore(); return; }
          lastTs = ts;
          let placements: Placement[] = [];
          const aspect = cutout.naturalWidth && cutout.naturalHeight ? cutout.naturalWidth / cutout.naturalHeight : 1;
          if (tracker.face) {
            const r = tracker.face.detectForVideo(video, ts);
            if (r.faceLandmarks[0]) placements = placeOnFace(r.faceLandmarks[0], category, aspect);
          } else if (tracker.hand) {
            const r = tracker.hand.detectForVideo(video, ts);
            if (r.landmarks[0]) placements = placeOnHand(r.landmarks[0], category, aspect);
          }
          seen = placements.length ? Math.min(seen + 1, 10) : Math.max(seen - 1, 0);
          for (const p of placements) {
            ctx.save();
            ctx.translate(p.x * w, p.y * h);
            ctx.rotate(p.angle);
            ctx.drawImage(cutout, -p.w * w / 2, -p.h * h / 2, p.w * w, p.h * h);
            ctx.restore();
          }
          ctx.restore();
          setState((s) => (s === 'frozen' ? s : seen > 0 ? 'tracking' : 'none'));
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
      tracker.face?.close(); tracker.hand?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, cutoutUrl]);

  const freeze = () => { frozen.current = !frozen.current; setState(frozen.current ? 'frozen' : 'tracking'); };
  const hint = usesFace(category) ? t('tryon_hint_face') : t('tryon_hint_hand');

  return (
    <div className="tryon" role="dialog" aria-label={t('tryon_title')}>
      <div className="tryon-head">
        <b>{t('tryon_title')} · {label}</b>
        <span className="sp" />
        <button className="k2-btn ghost" onClick={onClose}>{t('tryon_close')}</button>
      </div>
      <div className="tryon-stage">
        <video ref={videoRef} playsInline muted style={{ display: 'none' }} />
        <canvas ref={canvasRef} className="tryon-canvas" />
        <div className={`tryon-state ${state}`}>
          {state === 'starting' && t('tryon_starting')}
          {state === 'none' && hint}
          {state === 'tracking' && t('tryon_tracking')}
          {state === 'frozen' && t('tryon_frozen')}
          {state === 'error' && (err ?? t('error'))}
        </div>
      </div>
      <div className="tryon-foot">
        <button className="k2-btn" disabled={state === 'starting' || state === 'error'} onClick={freeze}>{state === 'frozen' ? t('tryon_resume') : t('tryon_snap')}</button>
        {onAskViewing && <button className="k2-btn gold" onClick={onAskViewing}>{t('kiosk_ask_viewing')}</button>}
        <p className="small muted">{t('tryon_privacy')}</p>
      </div>
    </div>
  );
}
