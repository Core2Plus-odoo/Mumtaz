'use strict';

const { searchRead } = require('../odoo/client');
const { getRegion, isTester, round2, today, monthStart } = require('../odoo/models');

/* ── System Prompt ──────────────────────────────────────────────── */
const SYSTEM_PROMPT = `You are Ayaz, the Commercial Director Agent for AJ Arabia Enterprise (WIDIAN brand).
You have live access to the company's Odoo ERP via your tools. Use them every time — never answer commercial questions from memory.

Your communication style:
- Lead with the headline insight (who's growing, who's slipping, which SKU is dominant)
- Always group customers by region: MENA · Europe · CIS · Asia & Oceania · Americas
- Distinguish FP (full-price) vs tester/sample units clearly — testers do not count as revenue units
- Compare to prior period whenever possible
- Flag dormant accounts proactively
- Use ranked tables for customer/SKU lists; highlight top 3 and bottom 3

When the question benefits from a chart, output a JSON block at the END of your response:
\`\`\`chart
{"type":"bar","title":"Revenue by Region","data":[{"label":"MENA","value":850000},{"label":"Europe","value":420000}]}
\`\`\`
Types: "bar" (comparison), "donut" (share/mix), "line" (trend). Only include when genuinely useful.`;

/* ── Tool Definitions ───────────────────────────────────────────── */
const TOOLS = [
  {
    name: 'get_sales_summary',
    description: 'Returns revenue summary for a date range, grouped by customer, product, or region. Distinguishes FP vs tester units. Revenue in AED and native currency.',
    input_schema: {
      type: 'object',
      properties: {
        date_from: { type: 'string', description: 'ISO date YYYY-MM-DD. Defaults to first of current month.' },
        date_to:   { type: 'string', description: 'ISO date YYYY-MM-DD. Defaults to today.' },
        group_by:  { type: 'string', enum: ['customer', 'product', 'region'], description: 'Grouping dimension.' },
      },
      required: [],
    },
  },
  {
    name: 'get_top_skus',
    description: 'Returns top SKUs by revenue for a date range. Separates FP units from tester/sample units. Shows revenue share %.',
    input_schema: {
      type: 'object',
      properties: {
        date_from: { type: 'string', description: 'ISO date YYYY-MM-DD. Defaults to first of current month.' },
        date_to:   { type: 'string', description: 'ISO date YYYY-MM-DD. Defaults to today.' },
        limit:     { type: 'integer', description: 'Max SKUs to return. Default 20.' },
      },
      required: [],
    },
  },
  {
    name: 'get_dormant_customers',
    description: 'Finds customers who have not placed an order in the last N days. Returns last order date and value.',
    input_schema: {
      type: 'object',
      properties: {
        inactive_days: { type: 'integer', description: 'Number of days of inactivity. Default 60.' },
      },
      required: [],
    },
  },
  {
    name: 'get_order_pipeline',
    description: 'Returns the current sales order pipeline (confirmed + quotations not yet invoiced), with customer, amount, currency, region.',
    input_schema: { type: 'object', properties: {}, required: [] },
  },
];

/* ── Tool Implementations ───────────────────────────────────────── */

async function getSalesSummary(args, sessionId) {
  const dateFrom = args.date_from || monthStart();
  const dateTo   = args.date_to   || today();
  const groupBy  = args.group_by  || 'customer';

  const lines = await searchRead(
    'account.move.line',
    [
      ['move_id.move_type',    '=',  'out_invoice'],
      ['move_id.state',        '=',  'posted'],
      ['move_id.invoice_date', '>=', dateFrom],
      ['move_id.invoice_date', '<=', dateTo],
      ['display_type',         '=',  'product'],
    ],
    ['product_id', 'partner_id', 'quantity', 'price_subtotal',
     'currency_id', 'move_id', 'name'],
    { limit: 5000 },
    sessionId,
  );

  // Also fetch partner countries for region mapping
  const partnerIds = [...new Set(lines.map(l => l.partner_id ? l.partner_id[0] : null).filter(Boolean))];
  let countryMap   = {};
  if (partnerIds.length) {
    const partners = await searchRead(
      'res.partner',
      [['id', 'in', partnerIds]],
      ['id', 'country_id'],
      { limit: 500 },
      sessionId,
    );
    for (const p of partners) {
      countryMap[p.id] = p.country_id ? p.country_id[1] : 'Unknown';
    }
  }

  // Aggregate
  const agg = {};
  let totalRevenue = 0;

  for (const line of lines) {
    const isTst = isTester(line.product_id ? line.product_id[1] : line.name);
    const partnerId = line.partner_id ? line.partner_id[0] : 0;
    const country   = countryMap[partnerId] || 'Unknown';
    const region    = getRegion(country);

    let key;
    let label;
    if (groupBy === 'customer') {
      key   = String(partnerId);
      label = line.partner_id ? line.partner_id[1] : 'Unknown';
    } else if (groupBy === 'product') {
      key   = String(line.product_id ? line.product_id[0] : 0);
      label = line.product_id ? line.product_id[1] : line.name;
    } else {
      key   = region;
      label = region;
    }

    if (!agg[key]) {
      agg[key] = {
        name:           label,
        region:         groupBy === 'region' ? label : region,
        fp_units:       0,
        tester_units:   0,
        revenue_aed:    0,
        currency:       line.currency_id ? line.currency_id[1] : 'AED',
      };
    }

    if (isTst) {
      agg[key].tester_units += (line.quantity || 0);
    } else {
      agg[key].fp_units     += (line.quantity || 0);
      agg[key].revenue_aed  = round2(agg[key].revenue_aed + (line.price_subtotal || 0));
      totalRevenue          = round2(totalRevenue + (line.price_subtotal || 0));
    }
  }

  const items = Object.values(agg)
    .sort((a, b) => b.revenue_aed - a.revenue_aed)
    .map(item => ({
      ...item,
      fp_units:     Math.round(item.fp_units),
      tester_units: Math.round(item.tester_units),
      revenue_aed:  round2(item.revenue_aed),
    }));

  return {
    period:       { from: dateFrom, to: dateTo },
    group_by:     groupBy,
    total_revenue_aed: round2(totalRevenue),
    items,
    line_count:   lines.length,
  };
}

async function getTopSkus(args, sessionId) {
  const dateFrom = args.date_from || monthStart();
  const dateTo   = args.date_to   || today();
  const limit    = args.limit     || 20;

  const lines = await searchRead(
    'account.move.line',
    [
      ['move_id.move_type',    '=',  'out_invoice'],
      ['move_id.state',        '=',  'posted'],
      ['move_id.invoice_date', '>=', dateFrom],
      ['move_id.invoice_date', '<=', dateTo],
      ['display_type',         '=',  'product'],
    ],
    ['product_id', 'quantity', 'price_subtotal', 'name'],
    { limit: 10000 },
    sessionId,
  );

  const byProduct = {};
  let totalRevenue = 0;

  for (const line of lines) {
    const prodId   = line.product_id ? line.product_id[0] : 0;
    const prodName = line.product_id ? line.product_id[1] : (line.name || 'Unknown');
    const isTst    = isTester(prodName);

    if (!byProduct[prodId]) {
      byProduct[prodId] = { sku_name: prodName, fp_units: 0, tester_units: 0, revenue_aed: 0 };
    }

    if (isTst) {
      byProduct[prodId].tester_units += (line.quantity || 0);
    } else {
      byProduct[prodId].fp_units    += (line.quantity || 0);
      byProduct[prodId].revenue_aed  = round2(byProduct[prodId].revenue_aed + (line.price_subtotal || 0));
      totalRevenue                   = round2(totalRevenue + (line.price_subtotal || 0));
    }
  }

  const items = Object.values(byProduct)
    .sort((a, b) => b.revenue_aed - a.revenue_aed)
    .slice(0, limit)
    .map(item => ({
      ...item,
      fp_units:     Math.round(item.fp_units),
      tester_units: Math.round(item.tester_units),
      revenue_aed:  round2(item.revenue_aed),
      share_pct:    totalRevenue ? round2((item.revenue_aed / totalRevenue) * 100) : 0,
    }));

  return { period: { from: dateFrom, to: dateTo }, total_revenue_aed: round2(totalRevenue), items };
}

async function getDormantCustomers(args, sessionId) {
  const days    = args.inactive_days || 60;
  const cutoff  = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);

  // Get all customers
  const customers = await searchRead(
    'res.partner',
    [['customer_rank', '>', 0], ['is_company', '=', true]],
    ['id', 'name', 'country_id'],
    { limit: 1000 },
    sessionId,
  );

  // Get last invoice per customer
  const recentInvoices = await searchRead(
    'account.move',
    [
      ['move_type', '=',  'out_invoice'],
      ['state',     '=',  'posted'],
      ['invoice_date', '>=', cutoff],
    ],
    ['partner_id', 'invoice_date', 'amount_total'],
    { limit: 2000 },
    sessionId,
  );

  const activePartnerIds = new Set(recentInvoices.map(i => i.partner_id ? i.partner_id[0] : null).filter(Boolean));

  const dormant = customers.filter(c => !activePartnerIds.has(c.id));

  // For dormant customers, get their last invoice ever
  const dormantIds = dormant.map(c => c.id);
  let lastOrders   = {};

  if (dormantIds.length) {
    const lastInvoices = await searchRead(
      'account.move',
      [
        ['move_type',   '=',  'out_invoice'],
        ['state',       '=',  'posted'],
        ['partner_id',  'in', dormantIds],
      ],
      ['partner_id', 'invoice_date', 'amount_total', 'currency_id'],
      { limit: 5000, order: 'invoice_date desc' },
      sessionId,
    );

    for (const inv of lastInvoices) {
      const pid = inv.partner_id ? inv.partner_id[0] : null;
      if (pid && !lastOrders[pid]) {
        lastOrders[pid] = { date: inv.invoice_date, value: inv.amount_total, currency: inv.currency_id ? inv.currency_id[1] : 'AED' };
      }
    }
  }

  const results = dormant.map(c => ({
    partner_name:           c.name,
    country:                c.country_id ? c.country_id[1] : 'Unknown',
    region:                 getRegion(c.country_id ? c.country_id[1] : ''),
    last_order_date:        lastOrders[c.id] ? lastOrders[c.id].date  : null,
    last_order_value_aed:   lastOrders[c.id] ? round2(lastOrders[c.id].value) : null,
  })).sort((a, b) => {
    if (!a.last_order_date) return 1;
    if (!b.last_order_date) return -1;
    return new Date(a.last_order_date) - new Date(b.last_order_date);
  });

  return {
    inactive_days: days,
    cutoff_date:   cutoff,
    dormant_count: results.length,
    items:         results,
  };
}

async function getOrderPipeline(sessionId) {
  const orders = await searchRead(
    'sale.order',
    [['state', 'in', ['draft', 'sent', 'sale']]],
    ['name', 'partner_id', 'amount_total', 'currency_id', 'state', 'date_order', 'validity_date'],
    { limit: 200, order: 'amount_total desc' },
    sessionId,
  );

  // Get partner countries
  const partnerIds = [...new Set(orders.map(o => o.partner_id ? o.partner_id[0] : null).filter(Boolean))];
  let countryMap   = {};
  if (partnerIds.length) {
    const partners = await searchRead(
      'res.partner',
      [['id', 'in', partnerIds]],
      ['id', 'country_id'],
      { limit: 500 },
      sessionId,
    );
    for (const p of partners) countryMap[p.id] = p.country_id ? p.country_id[1] : 'Unknown';
  }

  const items = orders.map(o => {
    const partnerId = o.partner_id ? o.partner_id[0] : 0;
    const country   = countryMap[partnerId] || 'Unknown';
    return {
      ref:          o.name,
      customer:     o.partner_id ? o.partner_id[1] : 'Unknown',
      amount_total: round2(o.amount_total),
      currency:     o.currency_id ? o.currency_id[1] : 'AED',
      state:        o.state,
      date:         o.date_order ? o.date_order.slice(0, 10) : null,
      expires:      o.validity_date || null,
      region:       getRegion(country),
      country,
    };
  });

  const totalAed = round2(items.reduce((s, o) => s + o.amount_total, 0));
  return { items, total_pipeline_aed: totalAed, count: items.length };
}

/* ── Tool Dispatcher ────────────────────────────────────────────── */
async function executeTool(name, input, sessionId) {
  switch (name) {
    case 'get_sales_summary':    return getSalesSummary(input, sessionId);
    case 'get_top_skus':         return getTopSkus(input, sessionId);
    case 'get_dormant_customers': return getDormantCustomers(input, sessionId);
    case 'get_order_pipeline':   return getOrderPipeline(sessionId);
    default: throw new Error(`Unknown tool: ${name}`);
  }
}

module.exports = { SYSTEM_PROMPT, TOOLS, executeTool };
