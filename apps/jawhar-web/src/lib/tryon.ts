// Where a piece sits on a person, from face and hand landmarks. Pure
// functions over normalised landmarks (0..1 in the frame), so they are unit
// tested without a camera. MediaPipe face mesh indices: 152 chin, 10
// forehead, 234 / 454 cheeks at ear level, 132 / 361 jaw below the ears.
// Hand indices: 0 wrist, 5 / 9 / 13 / 17 finger bases, 13 / 14 ring finger.

export type Pt = { x: number; y: number; z?: number };
export type Placement = { x: number; y: number; w: number; h: number; angle: number };
export type Category = 'bangle' | 'chain' | 'necklace' | 'ring' | 'earrings' | 'bracelet' | 'pendant' | 'set' | 'coin';

const dist = (a: Pt, b: Pt) => Math.hypot(a.x - b.x, a.y - b.y);
const mid = (a: Pt, b: Pt): Pt => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
const angle = (a: Pt, b: Pt) => Math.atan2(b.y - a.y, b.x - a.x);

export const FACE_CATEGORIES: Category[] = ['chain', 'necklace', 'pendant', 'set', 'earrings'];
export const HAND_CATEGORIES: Category[] = ['ring', 'bangle', 'bracelet'];

export function usesFace(c: string | null | undefined) { return FACE_CATEGORIES.includes(c as Category); }
export function usesHand(c: string | null | undefined) { return HAND_CATEGORIES.includes(c as Category); }

/** Placements (one or two) for a face-worn piece. `aspect` is the cutout's width / height. */
export function placeOnFace(face: Pt[], category: Category, aspect: number): Placement[] {
  if (face.length < 468) return [];
  const chin = face[152], forehead = face[10], left = face[234], right = face[454];
  const faceW = dist(left, right);
  const faceH = dist(forehead, chin);
  const tilt = angle(left, right);
  if (category === 'earrings') {
    const lobeL = face[132], lobeR = face[361];
    const h = faceH * 0.42, w = h * aspect;
    return [lobeL, lobeR].map((p) => ({ x: p.x, y: p.y + h * 0.35, w, h, angle: tilt }));
  }
  // necklace, chain, pendant, set: hung below the chin, centred on the neck
  const scale = category === 'pendant' ? 0.9 : category === 'set' ? 1.9 : 1.5;
  const w = faceW * scale, h = w / aspect;
  const drop = category === 'pendant' ? 0.45 : 0.4;
  const centre = mid(left, right);
  return [{ x: chin.x + (chin.x - centre.x) * 0.2, y: chin.y + faceH * drop + h * 0.25, w, h, angle: tilt }];
}

/** Placement for a hand-worn piece. */
export function placeOnHand(hand: Pt[], category: Category, aspect: number): Placement[] {
  if (hand.length < 21) return [];
  const wrist = hand[0], indexBase = hand[5], pinkyBase = hand[17], middleBase = hand[9];
  const palmW = dist(indexBase, pinkyBase);
  const forearm = angle(wrist, middleBase);
  if (category === 'ring') {
    const a = hand[13], b = hand[14];
    const p = mid(a, b);
    const w = palmW * 0.42, h = w / aspect;
    return [{ x: p.x, y: p.y, w, h, angle: angle(a, b) + Math.PI / 2 }];
  }
  // bangle and bracelet sit just below the wrist, across the forearm
  const back = { x: wrist.x - (middleBase.x - wrist.x) * 0.35, y: wrist.y - (middleBase.y - wrist.y) * 0.35 };
  const w = palmW * (category === 'bangle' ? 1.35 : 1.25), h = w / aspect;
  return [{ x: back.x, y: back.y, w, h, angle: forearm + Math.PI / 2 }];
}
