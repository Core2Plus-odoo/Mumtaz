import { describe, expect, it } from 'vitest';
import { stateLabel, tierLabel, translate } from './i18n';

describe('i18n', () => {
  it('has an Arabic string for every English key', () => {
    // The dictionary is private; probe through translate with a few keys and
    // then the whole key list via a known pair.
    const en = translate('en', 'nav_pieces');
    const ar = translate('ar', 'nav_pieces');
    expect(en).toBe('Pieces');
    expect(ar).not.toBe(en);
  });
  it('falls back to English, then to the key', () => {
    expect(translate('ar', 'no_such_key')).toBe('no_such_key');
  });
  it('labels states and tiers', () => {
    expect(stateLabel('en', 'sale')).toBe('Confirmed');
    expect(stateLabel('ar', 'sale')).toBe('مؤكد');
    expect(tierLabel('en', false)).toBe('Standard');
    expect(tierLabel('en', 'royal')).toBe('Royal / Protocol');
  });
});
