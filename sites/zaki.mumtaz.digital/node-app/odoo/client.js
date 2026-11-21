'use strict';

const fetch = require('node-fetch');

let _reqId = 1;

function buildBody(params) {
  return JSON.stringify({ jsonrpc: '2.0', method: 'call', id: _reqId++, params });
}

function sessionHeaders(sessionId) {
  const h = { 'Content-Type': 'application/json' };
  if (sessionId) h['Cookie'] = `session_id=${sessionId}`;
  return h;
}

async function rpc(baseUrl, endpoint, params, sessionId) {
  let res;
  try {
    res = await fetch(`${baseUrl}${endpoint}`, {
      method:  'POST',
      headers: sessionHeaders(sessionId),
      body:    buildBody(params),
      timeout: 30000,
    });
  } catch (err) {
    throw new Error(`Cannot reach Odoo at ${baseUrl} — ${err.message}`);
  }

  const body = await res.json();

  if (body.error) {
    const msg = body.error.data?.message || JSON.stringify(body.error);
    if (msg.includes('session') || msg.includes('login') || res.status === 401) {
      const e = new Error('Odoo session expired. Please reconnect.');
      e.code = 'SESSION_EXPIRED';
      throw e;
    }
    throw new Error(`Odoo: ${msg}`);
  }

  const setCookie  = res.headers.get('set-cookie');
  const newSession = setCookie ? (setCookie.match(/session_id=([^;]+)/) || [])[1] : null;

  return { result: body.result, newSession };
}

async function authenticate(baseUrl, db, email, password) {
  const { result, newSession } = await rpc(baseUrl, '/web/session/authenticate', {
    db, login: email, password,
  }, null);

  if (!result || !result.uid) throw new Error('Invalid email or password.');

  return {
    uid:       result.uid,
    name:      result.name,
    sessionId: newSession || result.session_id,
  };
}

/* All data functions receive a `conn` object: { baseUrl, db, sessionId } */

async function searchRead(conn, model, domain, fields, opts = {}) {
  const { result } = await rpc(conn.baseUrl, '/web/dataset/call_kw', {
    model, method: 'search_read',
    args:   [domain],
    kwargs: { fields, limit: opts.limit ?? 500, offset: opts.offset ?? 0, order: opts.order ?? '' },
  }, conn.sessionId);
  return result;
}

async function read(conn, model, ids, fields) {
  const { result } = await rpc(conn.baseUrl, '/web/dataset/call_kw', {
    model, method: 'read', args: [ids], kwargs: { fields },
  }, conn.sessionId);
  return result;
}

async function callMethod(conn, model, method, args, kwargs = {}) {
  const { result } = await rpc(conn.baseUrl, '/web/dataset/call_kw', {
    model, method, args, kwargs,
  }, conn.sessionId);
  return result;
}

async function readGroup(conn, model, domain, fields, groupby, opts = {}) {
  const { result } = await rpc(conn.baseUrl, '/web/dataset/call_kw', {
    model,
    method: 'read_group',
    args:   [domain, fields, groupby],
    kwargs: { lazy: opts.lazy ?? false, orderby: opts.order ?? '', limit: opts.limit ?? 0 },
  }, conn.sessionId);
  return result;
}

module.exports = { authenticate, searchRead, read, callMethod, readGroup };
