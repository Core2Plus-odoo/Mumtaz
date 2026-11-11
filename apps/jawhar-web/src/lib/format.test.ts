import { describe, expect, it } from 'vitest';
import { grams, money, num, pct, when } from './format';

const AED = { code: 'AED', symbol: 'د.إ', decimals: 2 };

describe('format', () => {
  it('renders money in the viewer language without changing the figure', () => {
    expect(money(3449.23, AED, 'en')).toMatch(/3,449\.23/);
    // ar-AE keeps Latin digits (CLDR default for the Gulf); only the symbol
    // placement and grouping change.
    expect(money(3449.23, AED, 'ar')).toMatch(/3,449\.23|3٬449/);
    expect(money(null, AED, 'en')).toBe('—');
  });
  it('keeps three decimals for grams and one for percent', () => {
    expect(grams(12.3456, 'en')).toBe('12.346 g');
    expect(pct(15, 'en')).toBe('15.0%');
    expect(num(245.8, 'en')).toBe('245.80');
  });
  it('reads Odoo naive UTC timestamps and plain dates', () => {
    expect(when('2026-11-11 08:42:00', 'en')).toMatch(/11 Nov 2026/);
    expect(when('2026-11-12', 'en', false)).toMatch(/12 Nov 2026/);
    expect(when(null, 'en')).toBe('—');
  });
});
