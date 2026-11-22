import { describe, expect, it } from 'vitest';
import { bangleFit, bangleSize, braceletFit, chainFit, measureBody, measureFace, measureHand, ringFit, ringSizes, scaleFromIris, summarise, type Vis } from './fit';
import type { Pt } from './tryon';

const W = 960, H = 1280;
// a face whose irises are 40 px across → 0.2925 mm per px
function face(irisPx = 40): Pt[] {
  const pts: Pt[] = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5 }));
  pts[10] = { x: 0.5, y: 0.2 }; pts[152] = { x: 0.5, y: 0.6 };
  pts[234] = { x: 0.26, y: 0.42 }; pts[454] = { x: 0.74, y: 0.42 };   // 461 px ≈ 135 mm
  pts[469] = { x: 0.40, y: 0.35 }; pts[471] = { x: 0.40 + irisPx / W, y: 0.35 };
  pts[474] = { x: 0.58, y: 0.35 }; pts[476] = { x: 0.58 + irisPx / W, y: 0.35 };
  return pts;
}
function hand(spanPx = 240): Pt[] {
  const pts: Pt[] = Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.5 }));
  pts[0] = { x: 0.5, y: 0.9 }; pts[5] = { x: 0.4, y: 0.6 }; pts[17] = { x: 0.4 + spanPx / W, y: 0.6 }; pts[9] = { x: 0.5, y: 0.58 };
  return pts;
}
function pose(opts: { ankles?: boolean; shoulderPx?: number } = {}): Vis[] {
  const pts: Vis[] = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, visibility: 0 }));
  const sw = (opts.shoulderPx ?? 1230) / W;
  pts[0] = { x: 0.5, y: 0.12, visibility: 1 }; pts[2] = { x: 0.48, y: 0.10, visibility: 1 }; pts[5] = { x: 0.52, y: 0.10, visibility: 1 };
  pts[11] = { x: 0.5 - sw / 2, y: 0.25, visibility: 1 }; pts[12] = { x: 0.5 + sw / 2, y: 0.25, visibility: 1 };
  if (opts.ankles) { pts[27] = { x: 0.45, y: 0.96, visibility: 1 }; pts[28] = { x: 0.55, y: 0.96, visibility: 1 }; }
  return pts;
}

describe('the iris ruler', () => {
  it('reads millimetres per pixel from the irises', () => {
    const s = scaleFromIris(face(), W, H)!;
    expect(s.mmPerPx).toBeCloseTo(11.7 / 40, 4);
  });
  it('refuses a face too small to trust and a non-face', () => {
    const f = face(); f[471] = { x: f[469].x + 3 / W, y: 0.35 }; f[476] = { x: f[474].x + 3 / W, y: 0.35 };
    expect(scaleFromIris(f, W, H)).toBeNull();
    expect(scaleFromIris(face().slice(0, 468), W, H)).toBeNull();
  });
});

describe('measurements', () => {
  const s = scaleFromIris(face(), W, H)!;
  it('reads a face about 135 mm wide and a neck around 345 mm', () => {
    const m = measureFace(face(), s, W, H);
    expect(m.faceWidthMm).toBeCloseTo(134.8, 0);
    expect(m.neckGirthMm).toBeGreaterThan(330); expect(m.neckGirthMm).toBeLessThan(360);
    expect(m.neckBase.y).toBeGreaterThan(0.6);
  });
  it('sizes a hand: ring, wrist and bangle', () => {
    const m = measureHand(hand(), s, W, H);           // 240 px span ≈ 70 mm → hand breadth ≈ 83 mm
    expect(m.handBreadthMm).toBeCloseTo(82.8, 0);
    expect(m.ringGirthMm).toBeGreaterThan(50); expect(m.ringGirthMm).toBeLessThan(60);
    expect(m.wristGirthMm).toBeGreaterThan(150); expect(m.wristGirthMm).toBeLessThan(175);
    expect(m.bangleDiameterMm).toBeGreaterThan(60); expect(m.bangleDiameterMm).toBeLessThan(68);
  });
  it('estimates height from the shoulders when only the torso is in the frame', () => {
    const b = measureBody(pose(), s, W, H)!;          // 1230 px ≈ 360 mm shoulders
    expect(b.method).toBe('shoulders');
    expect(b.heightCm).toBe(160);
  });
  it('measures head to ankle when the whole body is in the frame', () => {
    // further from the camera: 8 px irises, 250 px shoulders ≈ 365 mm
    const far = scaleFromIris(face(8), W, H)!;
    const b = measureBody(pose({ ankles: true, shoulderPx: 250 }), far, W, H)!;
    expect(b.method).toBe('full_body');
    expect(b.heightCm).toBeGreaterThan(150); expect(b.heightCm).toBeLessThan(185);
  });
  it('gives nothing when the shoulders are hidden or not a torso', () => {
    const p = pose(); p[11].visibility = 0.1;
    expect(measureBody(p, s, W, H)).toBeNull();
    expect(measureBody(pose({ shoulderPx: 300 }), s, W, H)).toBeNull();
  });
});

describe('sizes and fit', () => {
  it('ring sizes: EU is the girth, US from it', () => {
    expect(ringSizes(54)).toEqual({ eu: 54, us: 7 });
    expect(ringSizes(49.3).us).toBe(5);
  });
  it('bangle size names by inner diameter', () => {
    expect(bangleSize(61).name).toBe('2-6');
    expect(bangleSize(55).name).toBe('2-2');
    expect(bangleSize(80).name).toBe('2-14');
  });
  it('where a chain sits on a 345 mm neck', () => {
    expect(chainFit(350, 345).sits).toBe('choker');
    expect(chainFit(420, 345).sits).toBe('collarbone');
    expect(chainFit(500, 345).sits).toBe('below_collarbone');
    expect(chainFit(600, 345).sits).toBe('bust');
    expect(chainFit(800, 345).sits).toBe('long');
  });
  it('tight, fits, loose', () => {
    expect(braceletFit(165, 155)).toBe('fits'); expect(braceletFit(160, 155)).toBe('tight'); expect(braceletFit(200, 155)).toBe('loose');
    expect(ringFit(17.2, 54)).toBe('fits'); expect(ringFit(16, 54)).toBe('tight'); expect(ringFit(19, 54)).toBe('loose');
    expect(bangleFit(63, 62)).toBe('fits'); expect(bangleFit(57, 62)).toBe('tight'); expect(bangleFit(72, 62)).toBe('loose');
  });
  it('summarises for a request, rounded, with the verdict for the piece being tried', () => {
    const s = scaleFromIris(face(), W, H)!;
    const out = summarise(measureBody(pose(), s, W, H), measureFace(face(), s, W, H), measureHand(hand(), s, W, H), { inner_diameter_mm: 63 }, 'bangle');
    expect(out.height_cm).toBe(160);
    expect(out.neck_girth_mm! % 5).toBe(0);
    expect(out.bangle).toMatch(/^2-/);
    expect(out.ring_eu).toBeGreaterThan(45);
    expect(out.verdict).toBe('fits');
    const chain = summarise(null, measureFace(face(), s, W, H), null, { length_mm: 450 }, 'chain');
    expect(chain.chain_sits).toBe('below_collarbone');
    expect(chain.verdict).toBeUndefined();
  });
});
