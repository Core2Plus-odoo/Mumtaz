import { describe, expect, it } from 'vitest';
import { placeOnFace, placeOnHand, usesFace, usesHand, type Pt } from './tryon';

function face(): Pt[] {
  const pts: Pt[] = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5 }));
  pts[10] = { x: 0.5, y: 0.2 }; pts[152] = { x: 0.5, y: 0.6 };
  pts[234] = { x: 0.35, y: 0.42 }; pts[454] = { x: 0.65, y: 0.42 };
  pts[132] = { x: 0.36, y: 0.5 }; pts[361] = { x: 0.64, y: 0.5 };
  return pts;
}
function hand(): Pt[] {
  const pts: Pt[] = Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.5 }));
  pts[0] = { x: 0.5, y: 0.9 }; pts[5] = { x: 0.42, y: 0.6 }; pts[9] = { x: 0.5, y: 0.58 };
  pts[13] = { x: 0.56, y: 0.6 }; pts[14] = { x: 0.58, y: 0.5 }; pts[17] = { x: 0.62, y: 0.64 };
  return pts;
}

describe('try-on placement', () => {
  it('knows which pieces go on a face and which on a hand', () => {
    expect(usesFace('earrings')).toBe(true); expect(usesFace('ring')).toBe(false);
    expect(usesHand('bangle')).toBe(true); expect(usesHand('coin')).toBe(false);
  });
  it('hangs a necklace below the chin, as wide as the face', () => {
    const [p] = placeOnFace(face(), 'necklace', 1);
    expect(p.y).toBeGreaterThan(0.6);
    expect(p.w).toBeCloseTo(0.45, 2);
    expect(p.x).toBeCloseTo(0.5, 2);
  });
  it('puts one earring on each ear', () => {
    const ps = placeOnFace(face(), 'earrings', 0.5);
    expect(ps).toHaveLength(2);
    expect(ps[0].x).toBeLessThan(0.5); expect(ps[1].x).toBeGreaterThan(0.5);
    expect(ps[0].y).toBeGreaterThan(0.5);
  });
  it('puts a ring on the ring finger and a bangle on the wrist', () => {
    const [ring] = placeOnHand(hand(), 'ring', 1);
    expect(ring.x).toBeCloseTo(0.57, 2);
    const [bangle] = placeOnHand(hand(), 'bangle', 1);
    expect(bangle.y).toBeGreaterThan(0.9);
    expect(bangle.w).toBeGreaterThan(ring.w);
  });
  it('returns nothing without landmarks', () => {
    expect(placeOnFace([], 'necklace', 1)).toEqual([]);
    expect(placeOnHand([], 'ring', 1)).toEqual([]);
  });
});
