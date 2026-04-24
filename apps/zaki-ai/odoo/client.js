'use strict';

const fetch = require('node-fetch');
require('dotenv').config();

const BASE_URL  = process.env.ODOO_BASE_URL || 'https://aj-arabia.odoo.com';
const ODOO_DB   = process.env.ODOO_DB       || 'aj-arabia';

let _reqId = 1;

function buildBody(method, params) {
  return JSON.stringify({ jsonrpc: '2.0', method: 'call', id: _reqId++, params });
}

function sessionHeaders(sessionId) {
  const h = { 'Content-Type': 'application/json' };
  if (sessionId) h['Cookie'] = `session_id=${sessionId}`;
  return h;
}

async function rpc(endpoint, params, sessionId) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${endpoint}`, {
      method:  'POST',
      headers: sessionHeaders(sessionId),
      body:    buildBody('call', params),
      timeout: 30000,
    });
  } catch (err) {
    throw new Error(`Odoo network error: ${err.message}`);
  }

  const body = await res.json();

  if (body.error) {
    const msg = body.error.data?.message || JSON.stringify(body.error);
    if (msg.includes('session') || msg.includes('login') || res.status === 401) {
      const e = new Error('Odoo session expired. Please reconnect.');
      e.code = 'SESSION_EXPIRED';
      throw e;
    }
    throw new Error(`Odoo error: ${msg}`);
  }

  // Extract refreshed session cookie if Odoo rotates it
  const setCookie = res.headers.get('set-cookie');
  const newSession = setCookie ? (setCookie.match(/session_id=([^;]+)/) || [])[1] : null;

  return { result: body.result, newSession };
}

async function authenticate(email, password) {
  const { result, newSession } = await rpc('/web/session/authenticate', {
    db: ODOO_DB, login: email, password,
  }, null);

  if (!result || !result.uid) {
    throw new Error('Invalid email or password.');
  }

  return {
    uid:       result.uid,
    name:      result.name,
    sessionId: newSession || result.session_id,
  };
}

async function searchRead(model, domain, fields, opts = {}, sessionId) {
  const { result } = await rpc('/web/dataset/call_kw', {
    model,
    method:  'search_read',
    args:    [domain],
    kwargs:  {
      fields,
      limit:  opts.limit  ?? 500,
      offset: opts.offset ?? 0,
      order:  opts.order  ?? '',
    },
  }, sessionId);
  return result;
}

async function read(model, ids, fields, sessionId) {
  const { result } = await rpc('/web/dataset/call_kw', {
    model, method: 'read', args: [ids], kwargs: { fields },
  }, sessionId);
  return result;
}

async function callMethod(model, method, args, kwargs = {}, sessionId) {
  const { result } = await rpc('/web/dataset/call_kw', {
    model, method, args, kwargs,
  }, sessionId);
  return result;
}

async function readGroup(model, domain, fields, groupby, opts = {}, sessionId) {
  const { result } = await rpc('/web/dataset/call_kw', {
    model,
    method: 'read_group',
    args:   [domain, fields, groupby],
    kwargs: {
      lazy:    opts.lazy    ?? false,
      orderby: opts.order   ?? '',
      limit:   opts.limit   ?? 0,
    },
  }, sessionId);
  return result;
}

module.exports = { authenticate, searchRead, read, callMethod, readGroup };
