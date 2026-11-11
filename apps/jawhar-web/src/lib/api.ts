// The only place the app talks to the server. Every call goes to the Jawhar
// API (mumtaz_jewellery_api) on the same origin; the session cookie carries
// the sign-in. Figures arrive from Odoo and are displayed as received: this
// file has no arithmetic in it, by design.

export type Money = { code: string; symbol: string; decimals: number };
export type Ref = { id: number; name: string } | null;

export type User = {
  id: number; name: string; login: string; email: string | null; lang: string;
  tz: string | null; roles: string[];
  company: { id: number; name: string; currency: Money };
};
export type Rate = {
  id: number; rate_per_gram: number; currency: string; effective_at: string;
  source: string; state: string; created_by: Ref; approved_by: Ref; approved_at: string | null;
};
export type Piece = {
  id: number; serial: string; product: Ref; karat: string | false;
  gross_weight_g: number; stone_weight_g: number; net_weight_g: number; wastage_pct: number;
  making_type: string | false; making_value: number; stones_value: number;
  rfid_tag: string | null; certificate_ref: string | null; price_incl_vat: number;
  on_hand: number; location: Ref;
};
export type Breakdown = Record<string, number> & { rate_id: number; making_discount_pct: number };
export type PieceDetail = Piece & {
  breakdown: Breakdown | null; breakdown_unavailable?: string; rate?: Rate; memos: Memo[];
};
export type Memo = {
  id: number; name: string; client: Ref; pieces: { id: number; serial: string; product: Ref }[];
  date_out: string; return_by: string; state: string; insured_value: number;
};
export type Client = {
  id: number; name: string; tier: string | false; restricted: boolean; ai_autonomy_cap: number;
  relationship_manager: Ref; deputy: Ref; phone: string | null; email: string | null;
  city: string | null; no_marketing: boolean; lifetime_value: number;
};
export type ClientDetail = Client & {
  preferred_karats: string | null; typical_budget: number; taste_notes: string | null;
  discreet_billing: boolean;
  occasions: { id: number; kind: string; date: string; recurring: boolean; note: string | null }[];
  memos: Memo[]; orders: Order[];
};
export type Snapshot = {
  rate_id?: number; rate_per_gram: number; fine_weight_g: number; metal_value: number;
  wastage_value: number; making_charge: number; stones_value: number; priced_on: string;
};
export type OrderLine = {
  id: number; description: string; product: Ref; piece: { id: number; serial: string } | null;
  qty: number; price_unit: number; subtotal: number; tax: number; total: number;
  making_discount_pct: number; priced: boolean; snapshot: Snapshot | null;
};
export type Order = {
  id: number; name: string; client: Ref; salesperson: Ref; date: string; state: string;
  kind: 'quote' | 'order'; amount_untaxed: number; amount_tax: number; amount_total: number;
  currency: string; line_count: number; invoice_status: string;
  lines?: OrderLine[]; invoices?: Ref[];
};
export type InvoiceLine = {
  id: number; description: string; product: Ref; piece: { id: number; serial: string } | null;
  qty: number; price_unit: number; subtotal: number; total: number; snapshot: Snapshot | null;
};
export type Invoice = {
  id: number; name: string; client: Ref; date: string | null; due_date: string | null;
  state: string; payment_state: string; amount_untaxed: number; amount_tax: number;
  amount_total: number; amount_residual: number; currency: string; origin: string | null;
  lines?: InvoiceLine[];
};
export type OldGold = {
  id: number; name: string; client: Ref; date: string; gross_weight_g: number; karat: string;
  fine_weight_g: number; applied_rate_per_g: number; value: number; state: string;
};
export type Card = {
  id: number; kind: string; title: string; detail: string | null; recommendation: string | null;
  impact: string | null; priority: number; restricted: boolean; state: string;
  link: { model: string; id: number } | null;
};
export type Today = {
  rate: Rate | null; currency: Money; pieces_on_hand: number | null;
  stock_value_incl_vat: number | null; open_quotes: number | null;
  orders_this_month: { count: number; amount: number } | null;
  invoices_unpaid: { count: number; amount: number } | null;
  memos_out: number | null; old_gold_pending: number | null; cards_open: number | null;
  clients: { total: number; restricted: number } | null;
};
export type Page<T> = { items: T[]; total?: number };

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

const BASE = '/jawhar/v1';

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}) },
    ...init,
  });
  let body: { ok: boolean; data?: T; error?: { code: string; message: string } };
  try {
    body = await res.json();
  } catch {
    throw new ApiError(res.status, 'bad_response', `The server answered ${res.status} without JSON.`);
  }
  if (!res.ok || !body.ok) {
    const e = body.error || { code: 'error', message: `HTTP ${res.status}` };
    throw new ApiError(res.status, e.code, e.message);
  }
  return body.data as T;
}

const q = (params: Record<string, string | number | boolean | undefined | null>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') s.set(k, String(v));
  const out = s.toString();
  return out ? `?${out}` : '';
};

export const api = {
  health: () => call<{ service: string; version: string }>('/health'),
  login: (login: string, password: string) =>
    call<User>('/auth/login', { method: 'POST', body: JSON.stringify({ login, password }) }),
  logout: () => call<{ signed_out: boolean }>('/auth/logout', { method: 'POST', body: '{}' }),
  me: () => call<User>('/me'),
  today: () => call<Today>('/today'),
  rateCurrent: () => call<{ rate: Rate | null; reason?: string }>('/rates/current'),
  rates: (limit = 30) => call<Page<Rate>>(`/rates${q({ limit })}`),
  pieces: (p: { q?: string; karat?: string; on_hand?: boolean; limit?: number; offset?: number } = {}) =>
    call<Page<Piece>>(`/pieces${q(p)}`),
  piece: (id: number, discount?: number) => call<PieceDetail>(`/pieces/${id}${q({ discount })}`),
  clients: (p: { q?: string; tier?: string; limit?: number; offset?: number } = {}) =>
    call<Page<Client>>(`/clients${q(p)}`),
  client: (id: number) => call<ClientDetail>(`/clients/${id}`),
  quotes: (p: { limit?: number; offset?: number } = {}) => call<Page<Order>>(`/sales/quotes${q(p)}`),
  orders: (p: { limit?: number; offset?: number } = {}) => call<Page<Order>>(`/sales/orders${q(p)}`),
  order: (id: number) => call<Order>(`/sales/orders/${id}`),
  invoices: (p: { limit?: number; offset?: number } = {}) => call<Page<Invoice>>(`/sales/invoices${q(p)}`),
  invoice: (id: number) => call<Invoice>(`/sales/invoices/${id}`),
  memos: (state?: string) => call<Page<Memo>>(`/memos${q({ state })}`),
  oldGold: () => call<Page<OldGold>>('/old-gold'),
  cards: (state = 'open') => call<Page<Card>>(`/owner/cards${q({ state })}`),
};
