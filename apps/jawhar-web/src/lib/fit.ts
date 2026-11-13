// Fit and size from landmarks, on the device. Pure functions over
// normalised landmarks (0..1 in the frame) plus the frame size in pixels,
// so they are unit tested without a camera.
//
// The ruler is the iris: an adult iris is 11.7 mm across, with very little
// variation between people (Caton 1998; 11.4–12.0 mm), and MediaPipe's face
// mesh carries both irises (468–472 and 473–477). From that one known
// length every other distance in the frame can be read in millimetres, at
// the face's depth. Hands held near the face and shoulders at the same
// depth come out within a few percent; everything here is labelled
// "estimated" and is a starting point for the fitter, never a sale size.
//
// Anthropometric ratios used (adult women, mean values):
//   biacromial (shoulder) width ≈ 0.225 × stature
//   hand breadth across the metacarpal heads ≈ palm span between the
//   index and little-finger bases × 1.18 (landmarks sit at joint centres)
//   ring-finger breadth at the base ≈ palm span / 4 × 0.95
//   wrist breadth ≈ hand breadth × 0.68; wrist girth ≈ breadth × 2.9
//   a bangle must pass the folded hand: inner diameter ≈ knuckle girth / π,
//   knuckle girth ≈ hand breadth × 2.45

import type { Pt } from './tryon';

export const IRIS_MM = 11.7;
export type Scale = { mmPerPx: number; source: 'iris' };
export type Vis = Pt & { visibility?: number };

const px = (a: Pt, b: Pt, w: number, h: number) => Math.hypot((a.x - b.x) * w, (a.y - b.y) * h);

/** Millimetres per pixel, from the irises; null when the face is not there or the irises are too small to trust. */
export function scaleFromIris(face: Pt[], frameW: number, frameH: number): Scale | null {
  if (face.length < 478 || !frameW || !frameH) return null;
  // 469/471 and 474/476 are the horizontal extremes of each iris ring
  const l = px(face[469], face[471], frameW, frameH);
  const r = px(face[474], face[476], frameW, frameH);
  const d = l > 0 && r > 0 ? (l + r) / 2 : Math.max(l, r);
  if (d < 6) return null;                               // too far away or not a real face
  return { mmPerPx: IRIS_MM / d, source: 'iris' };
}

export type FaceMeasure = { faceWidthMm: number; neckGirthMm: number; neckBase: Pt };

/** The face in millimetres and where the neck base is (for draping a chain). */
export function measureFace(face: Pt[], scale: Scale, frameW: number, frameH: number): FaceMeasure {
  const faceWidthMm = px(face[234], face[454], frameW, frameH) * scale.mmPerPx;
  // neck girth ≈ 2.55 × bizygomatic face width (women, mean 135 mm face → 345 mm neck)
  const neckGirthMm = faceWidthMm * 2.55;
  const chin = face[152], forehead = face[10];
  const faceH = Math.hypot(chin.x - forehead.x, chin.y - forehead.y);
  const neckBase = { x: chin.x + (chin.x - (face[234].x + face[454].x) / 2) * 0.2, y: chin.y + faceH * 0.55 };
  return { faceWidthMm, neckGirthMm, neckBase };
}

export type HandMeasure = {
  handBreadthMm: number; fingerBreadthMm: number; wristBreadthMm: number; wristGirthMm: number;
  ringGirthMm: number; bangleDiameterMm: number;
};

/** The hand in millimetres: ring girth, wrist girth and the bangle it can pass. */
export function measureHand(hand: Pt[], scale: Scale, frameW: number, frameH: number): HandMeasure {
  const span = px(hand[5], hand[17], frameW, frameH) * scale.mmPerPx;
  const handBreadthMm = span * 1.18;
  const fingerBreadthMm = span / 4 * 0.95;
  const wristBreadthMm = handBreadthMm * 0.68;
  return {
    handBreadthMm, fingerBreadthMm, wristBreadthMm,
    wristGirthMm: wristBreadthMm * 2.9,
    ringGirthMm: fingerBreadthMm * Math.PI * 1.05,
    bangleDiameterMm: handBreadthMm * 2.45 / Math.PI,
  };
}

export type BodyMeasure = { shoulderWidthMm: number; heightCm: number; method: 'full_body' | 'shoulders'; shoulders: [Pt, Pt] | null };

/** Height from the pose: head-to-ankle when the whole body is in the frame, else from the shoulder width. */
export function measureBody(pose: Vis[], scale: Scale, frameW: number, frameH: number): BodyMeasure | null {
  if (pose.length < 33) return null;
  const vis = (i: number) => (pose[i].visibility ?? 1) >= 0.5;
  if (!vis(11) || !vis(12)) return null;
  const shoulderWidthMm = px(pose[11], pose[12], frameW, frameH) * scale.mmPerPx;
  if (shoulderWidthMm < 200) return null;              // not a torso at the face's depth
  const nose = pose[0], eyeMid = { x: (pose[2].x + pose[5].x) / 2, y: (pose[2].y + pose[5].y) / 2 };
  if (vis(27) && vis(28) && vis(0)) {
    // crown ≈ eyes raised by 1.3 × the eye-to-nose drop; ankles sit ~70 mm above the floor
    const crownY = eyeMid.y - Math.abs(nose.y - eyeMid.y) * 1.3 - 0.02;
    const ankleY = (pose[27].y + pose[28].y) / 2;
    const mm = (ankleY - crownY) * frameH * scale.mmPerPx + 70;
    if (mm > 1200 && mm < 2100) return { shoulderWidthMm, heightCm: Math.round(mm / 10), method: 'full_body', shoulders: [pose[11], pose[12]] };
  }
  return { shoulderWidthMm, heightCm: Math.round(shoulderWidthMm / 0.225 / 10), method: 'shoulders', shoulders: [pose[11], pose[12]] };
}

// -- sizes ---------------------------------------------------------------

/** EU ring size is the inner circumference in millimetres; US from the same circumference. */
export function ringSizes(girthMm: number) {
  const eu = Math.round(girthMm);
  const us = Math.round(((girthMm - 36.54) / 2.55) * 2) / 2;
  return { eu, us: Math.max(3, Math.min(13, us)) };
}

/** Gulf and Indian bangle sizes by inner diameter, as the trade names them. */
export const BANGLE_SIZES: [string, number][] = [
  ['2-2', 54], ['2-4', 57], ['2-6', 60], ['2-8', 63], ['2-10', 66], ['2-12', 70], ['2-14', 73],
];
export function bangleSize(diameterMm: number) {
  let best = BANGLE_SIZES[0];
  for (const s of BANGLE_SIZES) if (Math.abs(s[1] - diameterMm) < Math.abs(best[1] - diameterMm)) best = s;
  return { name: best[0], diameter_mm: best[1] };
}

export type ChainFit = { dropMm: number; sits: 'choker' | 'collarbone' | 'below_collarbone' | 'bust' | 'long' };

/** Where a chain of this length sits on this neck: how far below the neck base, and the name of the length. */
export function chainFit(lengthMm: number, neckGirthMm: number): ChainFit {
  const drop = Math.max(0, (lengthMm - neckGirthMm) / 2);
  const sits = drop < 15 ? 'choker' : drop < 45 ? 'collarbone' : drop < 80 ? 'below_collarbone' : drop < 140 ? 'bust' : 'long';
  return { dropMm: Math.round(drop), sits };
}

/** A bracelet is comfortable at wrist girth + 15–25 mm. */
export function braceletFit(lengthMm: number, wristGirthMm: number): 'tight' | 'fits' | 'loose' {
  const ease = lengthMm - wristGirthMm;
  return ease < 10 ? 'tight' : ease > 35 ? 'loose' : 'fits';
}

export function ringFit(innerDiameterMm: number, ringGirthMm: number): 'tight' | 'fits' | 'loose' {
  const diff = innerDiameterMm * Math.PI - ringGirthMm;
  return diff < -1.5 ? 'tight' : diff > 3 ? 'loose' : 'fits';
}

export function bangleFit(innerDiameterMm: number, bangleDiameterMm: number): 'tight' | 'fits' | 'loose' {
  const diff = innerDiameterMm - bangleDiameterMm;
  return diff < -2 ? 'tight' : diff > 6 ? 'loose' : 'fits';
}

// -- the summary that travels with a request --------------------------------

export type Dims = { length_mm?: number | null; inner_diameter_mm?: number | null; width_mm?: number | null };
export type FitSummary = {
  height_cm?: number; height_method?: BodyMeasure['method'];
  wrist_girth_mm?: number; bangle?: string; ring_eu?: number; ring_us?: number;
  neck_girth_mm?: number; chain_sits?: ChainFit['sits']; verdict?: 'tight' | 'fits' | 'loose';
};

/** Round to what a fitter would write down; nothing here is more precise than ±5%. */
export function summarise(body: BodyMeasure | null, face: FaceMeasure | null, hand: HandMeasure | null, dims: Dims | null, category: string): FitSummary {
  const s: FitSummary = {};
  if (body) { s.height_cm = body.heightCm; s.height_method = body.method; }
  if (face) {
    s.neck_girth_mm = Math.round(face.neckGirthMm / 5) * 5;
    if (dims?.length_mm && ['chain', 'necklace', 'pendant', 'set'].includes(category)) s.chain_sits = chainFit(dims.length_mm, face.neckGirthMm).sits;
  }
  if (hand) {
    s.wrist_girth_mm = Math.round(hand.wristGirthMm / 5) * 5;
    s.bangle = bangleSize(hand.bangleDiameterMm).name;
    const r = ringSizes(hand.ringGirthMm); s.ring_eu = r.eu; s.ring_us = r.us;
    if (category === 'ring' && dims?.inner_diameter_mm) s.verdict = ringFit(dims.inner_diameter_mm, hand.ringGirthMm);
    if (category === 'bangle' && dims?.inner_diameter_mm) s.verdict = bangleFit(dims.inner_diameter_mm, hand.bangleDiameterMm);
    if (category === 'bracelet' && dims?.length_mm) s.verdict = braceletFit(dims.length_mm, hand.wristGirthMm);
  }
  return s;
}
