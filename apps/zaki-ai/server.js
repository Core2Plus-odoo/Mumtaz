'use strict';

require('dotenv').config();

const express = require('express');
const session = require('express-session');
const cors    = require('cors');
const path    = require('path');
const { authenticate } = require('./odoo/client');
const zaki            = require('./agents/zaki');

const app  = express();
const PORT = process.env.PORT || 3000;

/* ── Middleware ─────────────────────────────────────────────────── */
app.use(cors({ origin: true, credentials: true }));
app.use(express.json({ limit: '2mb' }));
app.use(express.static(path.join(__dirname, 'public')));

app.use(session({
  secret:            process.env.SESSION_SECRET || 'zaki-dev-secret',
  resave:            false,
  saveUninitialized: false,
  cookie: {
    secure:   process.env.NODE_ENV === 'production',
    httpOnly: true,
    maxAge:   24 * 60 * 60 * 1000, // 24 hours
  },
}));

/* ── Auth Middleware ────────────────────────────────────────────── */
function requireAuth(req, res, next) {
  if (req.session && req.session.odooConn) return next();
  res.status(401).json({ error: 'Not authenticated', code: 'NOT_AUTHENTICATED' });
}

/* ── Auth Routes ────────────────────────────────────────────────── */
app.post('/auth/login', async (req, res) => {
  const { email, password, odooUrl, db } = req.body;
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password required.' });
  }
  if (!odooUrl || !db) {
    return res.status(400).json({ error: 'Odoo URL and database name required.' });
  }

  // Normalise URL — strip trailing slash
  const baseUrl = odooUrl.replace(/\/+$/, '');

  try {
    const { uid, name, sessionId } = await authenticate(baseUrl, db, email, password);
    req.session.odooConn  = { baseUrl, db, sessionId };
    req.session.odooUid   = uid;
    req.session.userName  = name;
    res.json({ ok: true, name, uid, baseUrl, db });
  } catch (err) {
    res.status(401).json({ error: err.message || 'Login failed.' });
  }
});

app.get('/auth/me', requireAuth, (req, res) => {
  const { baseUrl, db } = req.session.odooConn;
  res.json({
    name:    req.session.userName,
    uid:     req.session.odooUid,
    baseUrl,
    db,
  });
});

app.post('/auth/logout', (req, res) => {
  req.session.destroy(() => res.json({ ok: true }));
});

/* ── Chat Route (SSE streaming) ─────────────────────────────────── */
app.post('/api/chat', requireAuth, async (req, res) => {
  const { message, history = [] } = req.body;

  if (!message || !message.trim()) {
    return res.status(400).json({ error: 'Message is required.' });
  }

  // Sanitise history: keep last 20 turns, ensure correct role alternation
  const sanitisedHistory = sanitiseHistory(history);

  // Set up SSE
  res.setHeader('Content-Type',  'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection',    'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no'); // for nginx
  res.flushHeaders();

  const conn = req.session.odooConn;

  function writeSSE(data) {
    if (res.writableEnded) return;
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  }

  // Heartbeat to prevent proxy timeouts
  const heartbeat = setInterval(() => {
    if (!res.writableEnded) res.write(': heartbeat\n\n');
  }, 15000);

  try {
    await zaki.chat({ message: message.trim(), history: sanitisedHistory, conn, writeSSE });
  } catch (err) {
    console.error('[ZAKI] Chat error:', err);
    if (!res.writableEnded) {
      writeSSE({ type: 'error', message: `Something went wrong: ${err.message}` });
      writeSSE({ type: 'done' });
    }
  } finally {
    clearInterval(heartbeat);
    if (!res.writableEnded) res.end();
  }
});

/* ── Dashboard Data ─────────────────────────────────────────────── */
app.get('/api/dashboard', requireAuth, async (req, res) => {
  const conn = req.session.odooConn;
  const { searchRead } = require('./odoo/client');
  try {
    const [invoices, bills] = await Promise.all([
      searchRead(conn, 'account.move',
        [['move_type', '=', 'out_invoice'], ['state', '=', 'posted']],
        ['name', 'invoice_date', 'amount_total', 'currency_id', 'partner_id'],
        { limit: 200, order: 'invoice_date desc' }
      ),
      searchRead(conn, 'account.move',
        [['move_type', '=', 'in_invoice'], ['state', '=', 'posted']],
        ['name', 'invoice_date', 'amount_total', 'currency_id', 'partner_id'],
        { limit: 200, order: 'invoice_date desc' }
      ),
    ]);

    let id = 1;
    const transactions = [
      ...invoices.map(inv => ({
        id: id++,
        date:        (inv.invoice_date || '').slice(0, 10),
        type:        'income',
        amount:      inv.amount_total || 0,
        category:    'Invoice',
        description: (inv.partner_id ? inv.partner_id[1] + ' — ' : '') + inv.name,
        currency:    inv.currency_id ? inv.currency_id[1] : 'AED',
      })),
      ...bills.map(bill => ({
        id: id++,
        date:        (bill.invoice_date || '').slice(0, 10),
        type:        'expense',
        amount:      bill.amount_total || 0,
        category:    'Bill',
        description: (bill.partner_id ? bill.partner_id[1] + ' — ' : '') + bill.name,
        currency:    bill.currency_id ? bill.currency_id[1] : 'AED',
      })),
    ].sort((a, b) => b.date.localeCompare(a.date));

    res.json({ transactions });
  } catch (err) {
    console.error('[Dashboard]', err.message);
    res.status(502).json({ error: err.message });
  }
});

/* ── Company Info ───────────────────────────────────────────────── */
app.get('/api/company', requireAuth, async (req, res) => {
  const conn = req.session.odooConn;
  const { searchRead } = require('./odoo/client');
  try {
    const rows = await searchRead(conn, 'res.company', [],
      ['name', 'website', 'email', 'phone', 'street', 'city', 'country_id'],
      { limit: 1 }
    );
    res.json(rows[0] || {});
  } catch (err) {
    console.error('[Company]', err.message);
    res.status(502).json({ error: err.message });
  }
});

/* ── Financial KPIs ─────────────────────────────────────────────── */
app.get('/api/financials', requireAuth, async (req, res) => {
  const conn = req.session.odooConn;
  const { searchRead } = require('./odoo/client');
  const year = new Date().getFullYear();
  const startOfYear = `${year}-01-01`;

  try {
    const [invoices, bills] = await Promise.all([
      searchRead(conn, 'account.move',
        [['move_type', '=', 'out_invoice'], ['state', '=', 'posted'], ['invoice_date', '>=', startOfYear]],
        ['name', 'invoice_date', 'amount_total', 'currency_id', 'partner_id', 'payment_state'],
        { limit: 1000, order: 'invoice_date desc' }
      ),
      searchRead(conn, 'account.move',
        [['move_type', '=', 'in_invoice'], ['state', '=', 'posted'], ['invoice_date', '>=', startOfYear]],
        ['name', 'invoice_date', 'amount_total', 'currency_id', 'partner_id'],
        { limit: 1000, order: 'invoice_date desc' }
      ),
    ]);

    const monthly = {};
    for (let m = 1; m <= 12; m++) monthly[m] = { revenue: 0, expenses: 0 };

    let totalRevenue = 0, totalExpenses = 0, unpaidCount = 0, unpaidAmount = 0;
    const customerMap = {};

    for (const inv of invoices) {
      const m = new Date(inv.invoice_date || Date.now()).getMonth() + 1;
      monthly[m].revenue += inv.amount_total || 0;
      totalRevenue += inv.amount_total || 0;
      if (inv.payment_state === 'not_paid' || inv.payment_state === 'partial') {
        unpaidCount++;
        unpaidAmount += inv.amount_total || 0;
      }
      const cust = inv.partner_id ? inv.partner_id[1] : 'Unknown';
      customerMap[cust] = (customerMap[cust] || 0) + (inv.amount_total || 0);
    }

    for (const bill of bills) {
      const m = new Date(bill.invoice_date || Date.now()).getMonth() + 1;
      monthly[m].expenses += bill.amount_total || 0;
      totalExpenses += bill.amount_total || 0;
    }

    const topCustomers = Object.entries(customerMap)
      .sort((a, b) => b[1] - a[1]).slice(0, 5)
      .map(([name, amount]) => ({ name, amount }));

    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const chartData = months.map((month, i) => ({
      month,
      revenue:  Math.round(monthly[i + 1].revenue),
      expenses: Math.round(monthly[i + 1].expenses),
    }));

    const currency = invoices[0]?.currency_id?.[1] || bills[0]?.currency_id?.[1] || 'AED';

    res.json({
      totalRevenue:  Math.round(totalRevenue),
      totalExpenses: Math.round(totalExpenses),
      netIncome:     Math.round(totalRevenue - totalExpenses),
      invoiceCount:  invoices.length,
      billCount:     bills.length,
      unpaidCount,
      unpaidAmount:  Math.round(unpaidAmount),
      topCustomers,
      chartData,
      currency,
      year,
    });
  } catch (err) {
    console.error('[Financials]', err.message);
    res.status(502).json({ error: err.message });
  }
});

/* ── SEO / PageSpeed Analysis ───────────────────────────────────── */
app.get('/api/seo', requireAuth, async (req, res) => {
  const { url } = req.query;
  if (!url) return res.status(400).json({ error: 'URL required' });

  const https = require('https');

  function fetchPS(strategy) {
    return new Promise((resolve, reject) => {
      const endpoint = `https://www.googleapis.com/pagespeedonline/v5/runPagespeed` +
        `?url=${encodeURIComponent(url)}&strategy=${strategy}` +
        `&category=performance&category=seo&category=accessibility&category=best-practices`;
      https.get(endpoint, (r) => {
        let raw = '';
        r.on('data', d => raw += d);
        r.on('end', () => {
          try { resolve(JSON.parse(raw)); }
          catch { reject(new Error('Invalid response from PageSpeed')); }
        });
      }).on('error', reject);
    });
  }

  function extract(result) {
    const cats   = result.lighthouseResult?.categories || {};
    const audits = result.lighthouseResult?.audits || {};
    return {
      performance:   Math.round((cats.performance?.score   || 0) * 100),
      seo:           Math.round((cats.seo?.score           || 0) * 100),
      accessibility: Math.round((cats.accessibility?.score || 0) * 100),
      bestPractices: Math.round((cats['best-practices']?.score || 0) * 100),
      lcp:  audits['largest-contentful-paint']?.displayValue || 'N/A',
      cls:  audits['cumulative-layout-shift']?.displayValue  || 'N/A',
      tbt:  audits['total-blocking-time']?.displayValue      || 'N/A',
      fcp:  audits['first-contentful-paint']?.displayValue   || 'N/A',
      ttfb: audits['server-response-time']?.displayValue     || 'N/A',
      si:   audits['speed-index']?.displayValue              || 'N/A',
    };
  }

  try {
    const [mobile, desktop] = await Promise.all([fetchPS('mobile'), fetchPS('desktop')]);
    res.json({ url, mobile: extract(mobile), desktop: extract(desktop) });
  } catch (err) {
    console.error('[SEO]', err.message);
    res.status(502).json({ error: err.message });
  }
});

/* ── CEO Dashboard page ─────────────────────────────────────────── */
app.get('/ceo', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'ceo.html'));
});

/* ── Health Check ───────────────────────────────────────────────── */
app.get('/health', (req, res) => res.json({ status: 'ok', service: 'zaki-ai' }));

/* ── Catch-all → serve index.html ──────────────────────────────── */
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

/* ── Helpers ────────────────────────────────────────────────────── */
function sanitiseHistory(raw) {
  if (!Array.isArray(raw)) return [];

  const cleaned = raw
    .filter(m => m && (m.role === 'user' || m.role === 'assistant') && m.content)
    .map(m => ({
      role:    m.role,
      content: typeof m.content === 'string' ? m.content : String(m.content),
    }));

  // Claude requires alternating roles; deduplicate consecutive same-role messages
  const result = [];
  for (const msg of cleaned) {
    if (result.length && result[result.length - 1].role === msg.role) continue;
    result.push(msg);
  }

  // Must start with user turn
  while (result.length && result[0].role !== 'user') result.shift();

  // Keep last 20 turns (10 exchanges)
  return result.slice(-20);
}

/* ── Start ──────────────────────────────────────────────────────── */
app.listen(PORT, () => {
  console.log(`\n🟡 ZAKI AI — AJ Arabia\n   http://localhost:${PORT}\n`);
  if (!process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_API_KEY === 'your_anthropic_api_key_here') {
    console.warn('   ⚠️  ANTHROPIC_API_KEY not set in .env');
  }
});
