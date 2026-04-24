'use strict';

const { searchRead, readGroup } = require('../odoo/client');
const { BANK_CODES, round2, agingBucket, today, monthStart } = require('../odoo/models');

/* ── System Prompt ──────────────────────────────────────────────── */
const SYSTEM_PROMPT = `You are Farid, the CFO Agent for AJ Arabia Enterprise.
You have live access to the company's Odoo ERP via your tools. Use them every time — never answer financial questions from memory or estimates.

Your communication style:
- Lead with the headline number, then drill into detail
- Always cite the Odoo source (account code, invoice ref, journal entry)
- Present amounts in AED by default; show native currency alongside for EUR/USD balances
- Flag anything unusual proactively (overdue >90 days, concentration risk, large unexplained movement)
- Use concise tables for lists; keep narrative tight

When the question involves charts, output a JSON block at the END of your response like this:
\`\`\`chart
{"type":"bar","title":"Bank Balances (AED)","data":[{"label":"ENBD AED","value":1234567}]}
\`\`\`
Types: "bar", "donut", "line". Only output a chart block when it genuinely adds value.`;

/* ── Tool Definitions ───────────────────────────────────────────── */
const TOOLS = [
  {
    name: 'get_bank_balances',
    description: 'Fetches current balances for all company bank accounts (codes 101100, 101200, 101300, 105100, 105110). Returns account name, currency, and AED-equivalent balance.',
    input_schema: { type: 'object', properties: {}, required: [] },
  },
  {
    name: 'get_aged_receivables',
    description: 'Returns all outstanding customer invoices grouped by customer and aging bucket (Current, 1-30, 31-60, 61-90, 91-120, 120+ days). Includes invoice references.',
    input_schema: {
      type: 'object',
      properties: {
        as_of_date: { type: 'string', description: 'ISO date (YYYY-MM-DD). Defaults to today.' },
      },
      required: [],
    },
  },
  {
    name: 'get_aged_payables',
    description: 'Returns all outstanding supplier bills grouped by supplier and due date. Flags overdue items.',
    input_schema: {
      type: 'object',
      properties: {
        as_of_date: { type: 'string', description: 'ISO date (YYYY-MM-DD). Defaults to today.' },
      },
      required: [],
    },
  },
  {
    name: 'get_fff_position',
    description: 'Returns the Five Fine Fragrance (FFF) total exposure: outstanding bills in EUR plus any advances paid on account (131xxx accounts). Includes last payment reference.',
    input_schema: { type: 'object', properties: {}, required: [] },
  },
  {
    name: 'get_pl_summary',
    description: 'Returns P&L summary (Revenue, COGS, Gross Margin, OPEX, Net) for a given period. All figures in AED.',
    input_schema: {
      type: 'object',
      properties: {
        date_from: { type: 'string', description: 'ISO date YYYY-MM-DD. Defaults to first of current month.' },
        date_to:   { type: 'string', description: 'ISO date YYYY-MM-DD. Defaults to today.' },
      },
      required: [],
    },
  },
  {
    name: 'get_currency_rates',
    description: 'Returns current exchange rates for active currencies (EUR, USD, etc.) against AED.',
    input_schema: { type: 'object', properties: {}, required: [] },
  },
];

/* ── Tool Implementations ───────────────────────────────────────── */

async function getBankBalances(sessionId) {
  const accounts = await searchRead(
    'account.account',
    [['code', 'in', BANK_CODES]],
    ['id', 'code', 'name', 'currency_id'],
    { limit: 20 },
    sessionId,
  );

  if (!accounts.length) return { error: 'No bank accounts found for the configured codes.' };

  const accountIds  = accounts.map(a => a.id);
  const accountById = Object.fromEntries(accounts.map(a => [a.id, a]));

  // Aggregate debit/credit per account from posted move lines
  const groups = await readGroup(
    'account.move.line',
    [['account_id', 'in', accountIds], ['parent_state', '=', 'posted']],
    ['account_id', 'debit', 'credit'],
    ['account_id'],
    {},
    sessionId,
  );

  const results = accounts.map(acc => {
    const g = groups.find(g => g.account_id && g.account_id[0] === acc.id);
    const balance = g ? round2((g.debit || 0) - (g.credit || 0)) : 0;
    return {
      account:        `${acc.code} — ${acc.name}`,
      currency:       acc.currency_id ? acc.currency_id[1] : 'AED',
      balance:        balance,
      aed_equivalent: balance, // FX conversion applied separately if currency != AED
    };
  });

  const total = round2(results.reduce((s, r) => s + r.aed_equivalent, 0));
  return { accounts: results, total_aed: total };
}

async function getAgedReceivables(args, sessionId) {
  const asOf = args.as_of_date || today();

  const invoices = await searchRead(
    'account.move',
    [
      ['move_type',     '=',  'out_invoice'],
      ['state',         '=',  'posted'],
      ['payment_state', 'not in', ['paid', 'in_payment']],
      ['invoice_date',  '<=', asOf],
    ],
    ['name', 'partner_id', 'currency_id', 'amount_residual', 'amount_residual_signed',
     'invoice_date_due', 'invoice_date', 'amount_total'],
    { limit: 500, order: 'invoice_date_due asc' },
    sessionId,
  );

  if (!invoices.length) return { message: `No outstanding receivables as of ${asOf}.`, items: [], total_aed: 0 };

  // Group by partner
  const byPartner = {};
  for (const inv of invoices) {
    const partner = inv.partner_id ? inv.partner_id[1] : 'Unknown';
    const bucket  = agingBucket(inv.invoice_date_due);
    if (!byPartner[partner]) byPartner[partner] = { partner, total_aed: 0, buckets: {}, invoices: [] };
    byPartner[partner].total_aed         = round2(byPartner[partner].total_aed + (inv.amount_residual || 0));
    byPartner[partner].buckets[bucket]   = round2((byPartner[partner].buckets[bucket] || 0) + (inv.amount_residual || 0));
    byPartner[partner].invoices.push({
      ref:      inv.name,
      date:     inv.invoice_date,
      due:      inv.invoice_date_due,
      currency: inv.currency_id ? inv.currency_id[1] : 'AED',
      amount:   round2(inv.amount_residual),
      bucket,
    });
  }

  const items     = Object.values(byPartner).sort((a, b) => b.total_aed - a.total_aed);
  const total_aed = round2(items.reduce((s, i) => s + i.total_aed, 0));
  return { as_of: asOf, items, total_aed, count: invoices.length };
}

async function getAgedPayables(args, sessionId) {
  const asOf = args.as_of_date || today();

  const bills = await searchRead(
    'account.move',
    [
      ['move_type',     '=',  'in_invoice'],
      ['state',         '=',  'posted'],
      ['payment_state', 'not in', ['paid', 'in_payment']],
      ['invoice_date',  '<=', asOf],
    ],
    ['name', 'partner_id', 'currency_id', 'amount_residual', 'invoice_date_due', 'invoice_date'],
    { limit: 500, order: 'invoice_date_due asc' },
    sessionId,
  );

  if (!bills.length) return { message: `No outstanding payables as of ${asOf}.`, items: [], total_aed: 0 };

  const byPartner = {};
  for (const bill of bills) {
    const partner = bill.partner_id ? bill.partner_id[1] : 'Unknown';
    const bucket  = agingBucket(bill.invoice_date_due);
    const overdue = new Date(bill.invoice_date_due) < new Date();
    if (!byPartner[partner]) byPartner[partner] = { partner, total_aed: 0, bills: [] };
    byPartner[partner].total_aed = round2(byPartner[partner].total_aed + (bill.amount_residual || 0));
    byPartner[partner].bills.push({
      ref:      bill.name,
      date:     bill.invoice_date,
      due:      bill.invoice_date_due,
      currency: bill.currency_id ? bill.currency_id[1] : 'AED',
      amount:   round2(bill.amount_residual),
      bucket,
      overdue,
    });
  }

  const items     = Object.values(byPartner).sort((a, b) => b.total_aed - a.total_aed);
  const total_aed = round2(items.reduce((s, i) => s + i.total_aed, 0));
  return { as_of: asOf, items, total_aed, count: bills.length };
}

async function getFffPosition(sessionId) {
  // 1. Outstanding bills from FFF suppliers
  const bills = await searchRead(
    'account.move',
    [
      ['move_type',     '=',  'in_invoice'],
      ['state',         '=',  'posted'],
      ['payment_state', 'not in', ['paid', 'in_payment']],
      ['partner_id.name', 'ilike', 'five fine fragrance'],
    ],
    ['name', 'currency_id', 'amount_residual', 'invoice_date_due', 'invoice_date', 'ref'],
    { limit: 100 },
    sessionId,
  );

  // 2. Advances on account (131xxx account codes)
  const advanceLines = await searchRead(
    'account.move.line',
    [
      ['account_id.code', 'like', '131'],
      ['partner_id.name', 'ilike', 'five fine fragrance'],
      ['parent_state',    '=',    'posted'],
    ],
    ['name', 'debit', 'credit', 'currency_id', 'amount_currency', 'move_id', 'date', 'ref'],
    { limit: 100 },
    sessionId,
  );

  const billsEur     = round2(bills.reduce((s, b) => s + (b.amount_residual || 0), 0));
  const advancesEur  = round2(advanceLines.reduce((s, l) => s + ((l.debit || 0) - (l.credit || 0)), 0));
  const lastBill     = bills.sort((a, b) => new Date(b.invoice_date) - new Date(a.invoice_date))[0];

  return {
    bills_eur:       billsEur,
    advances_eur:    advancesEur,
    net_exposure_eur: round2(billsEur - advancesEur),
    currency:        'EUR',
    last_invoice_ref: lastBill ? lastBill.name : null,
    last_invoice_date: lastBill ? lastBill.invoice_date : null,
    outstanding_bills: bills.map(b => ({
      ref:    b.name,
      due:    b.invoice_date_due,
      amount: round2(b.amount_residual),
    })),
  };
}

async function getPlSummary(args, sessionId) {
  const dateFrom = args.date_from || monthStart();
  const dateTo   = args.date_to   || today();

  // Revenue: posted customer invoices
  const invoices = await searchRead(
    'account.move',
    [
      ['move_type', '=',  'out_invoice'],
      ['state',     '=',  'posted'],
      ['invoice_date', '>=', dateFrom],
      ['invoice_date', '<=', dateTo],
    ],
    ['amount_untaxed', 'amount_total', 'currency_id'],
    { limit: 2000 },
    sessionId,
  );

  // Credit notes reduce revenue
  const creditNotes = await searchRead(
    'account.move',
    [
      ['move_type', '=',  'out_refund'],
      ['state',     '=',  'posted'],
      ['invoice_date', '>=', dateFrom],
      ['invoice_date', '<=', dateTo],
    ],
    ['amount_untaxed'],
    { limit: 500 },
    sessionId,
  );

  const grossRevenue = invoices.reduce((s, i) => s + (i.amount_untaxed || 0), 0);
  const returns      = creditNotes.reduce((s, c) => s + (c.amount_untaxed || 0), 0);
  const revenue      = round2(grossRevenue - returns);

  // COGS & OPEX from move lines (account code prefixes: 4xxx = COGS, 6xxx = OPEX)
  const expenseLines = await searchRead(
    'account.move.line',
    [
      ['parent_state',        '=',  'posted'],
      ['date',                '>=', dateFrom],
      ['date',                '<=', dateTo],
      ['account_id.code',     'like', '4'],  // starts with 4 (COGS)
      ['move_id.move_type',   'in', ['in_invoice', 'out_invoice', 'entry']],
    ],
    ['debit', 'credit', 'account_id'],
    { limit: 5000 },
    sessionId,
  );

  const opexLines = await searchRead(
    'account.move.line',
    [
      ['parent_state',      '=',  'posted'],
      ['date',              '>=', dateFrom],
      ['date',              '<=', dateTo],
      ['account_id.code',   'like', '6'],
    ],
    ['debit', 'credit'],
    { limit: 5000 },
    sessionId,
  );

  const cogs          = round2(expenseLines.reduce((s, l) => s + ((l.debit || 0) - (l.credit || 0)), 0));
  const opex          = round2(opexLines.reduce((s, l)    => s + ((l.debit || 0) - (l.credit || 0)), 0));
  const grossMargin   = round2(revenue - cogs);
  const grossMarginPct = revenue ? round2((grossMargin / revenue) * 100) : 0;
  const netPl         = round2(grossMargin - opex);

  return {
    period:         { from: dateFrom, to: dateTo },
    revenue_aed:    revenue,
    cogs_aed:       cogs,
    gross_margin_aed: grossMargin,
    gross_margin_pct: grossMarginPct,
    opex_aed:       opex,
    net_aed:        netPl,
    invoice_count:  invoices.length,
  };
}

async function getCurrencyRates(sessionId) {
  const currencies = await searchRead(
    'res.currency',
    [['active', '=', true]],
    ['name', 'rate', 'symbol', 'position'],
    { limit: 50 },
    sessionId,
  );
  const rates = {};
  for (const c of currencies) {
    // Odoo stores rate as 1 AED = N units of currency; inverse for display
    rates[c.name] = c.rate ? round2(1 / c.rate) : null;
  }
  return { rates, note: 'Rates are AED per 1 unit of foreign currency', fetched_at: new Date().toISOString() };
}

/* ── Tool Dispatcher ────────────────────────────────────────────── */
async function executeTool(name, input, sessionId) {
  switch (name) {
    case 'get_bank_balances':    return getBankBalances(sessionId);
    case 'get_aged_receivables': return getAgedReceivables(input, sessionId);
    case 'get_aged_payables':    return getAgedPayables(input, sessionId);
    case 'get_fff_position':     return getFffPosition(sessionId);
    case 'get_pl_summary':       return getPlSummary(input, sessionId);
    case 'get_currency_rates':   return getCurrencyRates(sessionId);
    default: throw new Error(`Unknown tool: ${name}`);
  }
}

module.exports = { SYSTEM_PROMPT, TOOLS, executeTool };
