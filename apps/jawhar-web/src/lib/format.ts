// Display formatting only. Nothing here changes a figure; it renders what the
// server sent, in the viewer's language.
import type { Money } from './api';

export function money(value: number | null | undefined, cur: Money | string, lang: string): string {
  if (value === null || value === undefined) return '—';
  const code = typeof cur === 'string' ? cur : cur.code;
  const decimals = typeof cur === 'string' ? 2 : cur.decimals;
  try {
    return new Intl.NumberFormat(lang === 'ar' ? 'ar-AE' : 'en-AE', {
      style: 'currency', currency: code, minimumFractionDigits: decimals, maximumFractionDigits: decimals,
    }).format(value);
  } catch {
    return `${value.toFixed(decimals)} ${code}`;
  }
}

export function num(value: number | null | undefined, lang: string, digits = 2): string {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat(lang === 'ar' ? 'ar-AE' : 'en-AE', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  }).format(value);
}

export function grams(value: number | null | undefined, lang: string): string {
  return value === null || value === undefined ? '—' : `${num(value, lang, 3)} g`;
}

export function when(iso: string | null | undefined, lang: string, withTime = true): string {
  if (!iso) return '—';
  // Odoo sends naive UTC timestamps ("2026-11-11 08:42:00") and plain dates.
  const d = new Date(iso.length > 10 ? iso.replace(' ', 'T') + 'Z' : iso + 'T00:00:00');
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(lang === 'ar' ? 'ar-AE' : 'en-GB', {
    dateStyle: 'medium', ...(withTime && iso.length > 10 ? { timeStyle: 'short' } : {}),
  }).format(d);
}

export function pct(value: number | null | undefined, lang: string): string {
  return value === null || value === undefined ? '—' : `${num(value, lang, 1)}%`;
}
