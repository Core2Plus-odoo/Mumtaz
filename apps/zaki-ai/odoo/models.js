'use strict';

const REGIONS = {
  'United Arab Emirates': 'MENA',  'Saudi Arabia':   'MENA',  'Kuwait':        'MENA',
  'Bahrain':              'MENA',  'Oman':           'MENA',  'Qatar':         'MENA',
  'Iraq':                 'MENA',  'Egypt':          'MENA',  'Morocco':       'MENA',
  'Russia':               'CIS',   'Azerbaijan':     'CIS',   'Ukraine':       'CIS',
  'Belarus':              'CIS',   'Georgia':        'CIS',   'Kazakhstan':    'CIS',
  'United Kingdom':       'Europe','Netherlands':    'Europe','Belgium':       'Europe',
  'Italy':                'Europe','Romania':        'Europe','Czech Republic':'Europe',
  'Malta':                'Europe','Poland':         'Europe','Hungary':       'Europe',
  'Albania':              'Europe','Cyprus':         'Europe','Germany':       'Europe',
  'France':               'Europe','Spain':          'Europe','Sweden':        'Europe',
  'Lithuania':            'Europe','Serbia':         'Europe',
  'United States':        'Americas','Canada':       'Americas',
  'South Korea':          'Asia & Oceania','India':  'Asia & Oceania',
  'Indonesia':            'Asia & Oceania','Australia':'Asia & Oceania',
  'Japan':                'Asia & Oceania','China':  'Asia & Oceania',
};

function getRegion(countryName) {
  return REGIONS[countryName] || 'Other';
}

function isTester(productName) {
  if (!productName) return false;
  const lc = productName.toLowerCase();
  return lc.includes('tester') || lc.includes('sample') || /\btest\b/.test(lc);
}

function round2(n) {
  return Math.round((n || 0) * 100) / 100;
}

function agingBucket(dueDateStr) {
  if (!dueDateStr) return 'No due date';
  const days = Math.floor((Date.now() - new Date(dueDateStr).getTime()) / 86400000);
  if (days <= 0)   return 'Current';
  if (days <= 30)  return '1-30 days';
  if (days <= 60)  return '31-60 days';
  if (days <= 90)  return '61-90 days';
  if (days <= 120) return '91-120 days';
  return '120+ days';
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function monthStart() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

const BANK_CODES = ['101100', '101200', '101300', '105100', '105110'];

module.exports = { REGIONS, getRegion, isTester, round2, agingBucket, today, monthStart, BANK_CODES };
