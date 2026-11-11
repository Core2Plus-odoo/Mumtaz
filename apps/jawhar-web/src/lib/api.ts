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
  id: number; serial: string; product: Ref; category: string | null; karat: string | false;
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
  lang: string | null; next_occasion: { kind: string; date: string; in_days: number } | null;
};
export type ClientDetail = Client & {
  trays: Tray[];
  preferred_karats: string | null; typical_budget: number; taste_notes: string | null;
  discreet_billing: boolean;
  occasions: { id: number; kind: string; date: string; recurring: boolean; note: string | null }[];
  memos: Memo[]; orders: Order[];
};
// --- the agents (plan v3 §12-13, wireframe 29) ---
export type AgentInfo = {
  key: 'zayan' | 'layla'; name: string; role: string; ceiling: string; purpose: string;
  tools: string[]; runs_today: number; waiting: number;
};
export type AiStatus = {
  agents: AgentInfo[]; tools: { name: string; agent: string; level: string; purpose: string }[];
  model: { configured: boolean; name: string | null }; paused: boolean; policy_version: string; can_pause: boolean;
  voice: Record<string, string>;
};
export type Refusal = { refused: string; message: string; agent?: string; tool?: string };
export type QueueItem = {
  kind: 'card' | 'draft'; id: number; title: string; detail: string | null; next: string | null;
  priority: number; owner: string; link: { model: string; id: number } | null;
};
export type Brief = {
  sentences: string[]; figures: Record<string, unknown> & { rate: { rate_per_gram: number; currency: string; approved_by: string; approved_at: string } | null; as_of: string };
  queue: QueueItem[]; sources: string[]; narrated_by: string; run_id: number; as_of: string; level: string;
} & Partial<Refusal>;
export type Draft = {
  id: number; name: string; kind: 'tray' | 'followup'; agent: 'zayan' | 'layla'; state: string;
  client: Ref; restricted: boolean; tray: Ref; channel: string; subject: string | null; owner: Ref;
  model_used: string; consent_ok: boolean; expired: boolean; expires_at: string | null; created_at: string;
  approved_by: Ref; approved_at: string | null; reasons: string[]; policy_version: string;
};
export type DraftDetail = Draft & {
  body: string; body_digest: string; review_note: string | null; sources: string[]; tray_detail: Tray | null;
};
export type AiRun = {
  id: number; at: string; agent: string; tool: string; level: string; user: Ref; client: Ref; draft: Ref;
  status: string; reason: string | null; model_used: string; input_tokens: number; output_tokens: number;
  duration_ms: number; sources: string[]; policy_version: string;
};
export type NewClient = {
  name: string; phone?: string; email?: string; city?: string; tier?: string; lang?: string;
  preferred_karats?: string; typical_budget?: number; no_marketing?: boolean; taste_notes?: string;
};
export type ChatMessage = { role: 'user' | 'agent'; text: string; links?: { label: string; to: string }[]; refused?: string; tool?: string };
export type ChatReply = { agent: string; intent: string; reply: string; links: { label: string; to: string }[]; model_used: string; refused?: string };
export type AskResult = {
  intent: string; agent: string; client: Ref; message?: string; brief?: Brief;
  rate?: { rate_per_gram: number; currency: string; approved_by: string; approved_at: string };
  queue?: QueueItem[]; tray_id?: number; draft_id?: number;
} & Partial<Refusal>;

export type Snapshot = {
  rate_id?: number; rate_per_gram: number; fine_weight_g: number; metal_value: number;
  wastage_value: number; making_charge: number; stones_value: number; priced_on: string;
};
export type OrderLine = {
  id: number; description: string; product: Ref; piece: { id: number; serial: string } | null;
  qty: number; price_unit: number; subtotal: number; tax: number; total: number;
  making_discount_pct: number; priced: boolean; margin: number | null; snapshot: Snapshot | null;
};
export type Order = {
  id: number; name: string; client: Ref; salesperson: Ref; date: string; state: string;
  kind: 'quote' | 'order'; amount_untaxed: number; amount_tax: number; amount_total: number;
  currency: string; line_count: number; invoice_status: string;
  validity_date: string | null; expired: boolean; old_gold: Ref;
  lines?: OrderLine[]; invoices?: Ref[];
};
export type PaymentMethod = { id: number; name: string; type: string };
export type Payment = { id: number; name: string; amount: number; journal: Ref; date: string; state: string };
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
  fine_weight_g: number; applied_rate_per_g: number; melt_loss_pct: number; buyback_discount_pct: number;
  value: number; state: string; approved_by: Ref; credited_on: Ref;
};
export type Availability = { status: 'on_shelf' | 'on_approval' | 'sold' | 'not_in_stock'; detail: unknown; client: Ref };
export type CounterPiece = PieceDetail & { availability: Availability };
export type Readiness = { ready: boolean; checks: { key: string; ok: boolean; detail: unknown }[] };
export type CounterResult = {
  order: Order; invoice: Invoice; payments: Payment[];
  deliveries: { id: number; name: string; state: string }[];
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
export type Lead = {
  id: number; name: string; client: Ref; stage: { id: number; name: string; sequence: number; won: boolean };
  probability: number; automated: boolean; expected_revenue: number; currency: string; salesperson: Ref;
  deadline: string | null; next_activity: { summary: string; date: string; user: Ref } | null; tray: Ref; created: string;
};
export type Pipeline = {
  stages: { id: number; name: string; won: boolean; count: number; value: number; weighted: number }[];
  items: Lead[];
  summary: { open: number; open_value: number; weighted: number; won_value: number; currency: string };
};
export type TrayLine = {
  id: number; piece: { id: number; serial: string; product: Ref; karat: string | false; net_weight_g: number };
  sequence: number; score: number; reasons: string[]; price: number; feedback: 'none' | 'like' | 'dislike';
  question: string | null; available: boolean;
};
export type Tray = {
  id: number; name: string; client: Ref; associate: Ref; state: string; intent: string | null; budget: number;
  piece_count: number; total: number; link_live: boolean; link_expires: string | null; link_opened_at: string | null;
  viewing_requested_at: string | null; viewing_preferred: string | null; viewing_note: string | null;
  reservation: Ref; lead: Ref; restricted: boolean; policy_version: string; stock_checked_at: string | null;
  lines?: TrayLine[];
};
export type PublicTray = {
  tray: string; expires: string; state: string; currency: string; viewing_requested: boolean;
  pieces: { ref: string; product: string; karat: string | false; net_weight_g: number; price: number; why: string; feedback: string; question: string | null }[];
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

async function callPublic<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}) },
    ...init,
  });
  let body: { ok: boolean; data?: T; error?: { code: string; message: string } };
  try { body = await res.json(); } catch { throw new ApiError(res.status, 'bad_response', `The server answered ${res.status} without JSON.`); }
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
  pieces: (p: { q?: string; karat?: string; on_hand?: boolean; category?: string; sort?: string; limit?: number; offset?: number } = {}) =>
    call<Page<Piece>>(`/pieces${q(p)}`),
  piece: (id: number, discount?: number) => call<PieceDetail>(`/pieces/${id}${q({ discount })}`),
  createClient: (p: NewClient) => call<ClientDetail>('/clients', { method: 'POST', body: JSON.stringify(p) }),
  clients: (p: { q?: string; tier?: string; sort?: string; city?: string; limit?: number; offset?: number } = {}) =>
    call<Page<Client>>(`/clients${q(p)}`),
  client: (id: number) => call<ClientDetail>(`/clients/${id}`),
  quotes: (p: { limit?: number; offset?: number } = {}) => call<Page<Order>>(`/sales/quotes${q(p)}`),
  orders: (p: { limit?: number; offset?: number } = {}) => call<Page<Order>>(`/sales/orders${q(p)}`),
  order: (id: number) => call<Order>(`/sales/orders/${id}`),
  invoices: (p: { limit?: number; offset?: number } = {}) => call<Page<Invoice>>(`/sales/invoices${q(p)}`),
  invoice: (id: number) => call<Invoice>(`/sales/invoices/${id}`),
  // --- the sale: writes. Level D: a person executes, under their name. ---
  createQuote: (client_id: number, lines: { piece_id: number; discount?: number }[]) =>
    call<Order>('/sales/quotes', { method: 'POST', body: JSON.stringify({ client_id, lines }) }),
  renewQuote: (id: number) => call<Order>(`/sales/quotes/${id}/renew`, { method: 'POST', body: '{}' }),
  confirmQuote: (id: number) => call<Order>(`/sales/quotes/${id}/confirm`, { method: 'POST', body: '{}' }),
  invoiceOrder: (id: number) => call<Invoice>(`/sales/orders/${id}/invoice`, { method: 'POST', body: '{}' }),
  paymentMethods: () => call<Page<PaymentMethod>>('/sales/payment-methods'),
  payInvoice: (id: number, p: { journal_id?: number; amount?: number }) =>
    call<{ invoice: Invoice; payments: Payment[] }>(`/sales/invoices/${id}/payments`, { method: 'POST', body: JSON.stringify(p) }),
  memos: (state?: string) => call<Page<Memo>>(`/memos${q({ state })}`),
  oldGold: (p: { client_id?: number; state?: string; unused?: boolean; limit?: number } = {}) =>
    call<Page<OldGold>>(`/old-gold${q(p)}`),
  createOldGold: (p: { client_id?: number; gross_weight_g: number; karat: string; melt_loss_pct?: number; buyback_discount_pct?: number }) =>
    call<OldGold>('/old-gold', { method: 'POST', body: JSON.stringify(p) }),
  approveOldGold: (id: number) => call<OldGold>(`/old-gold/${id}/approve`, { method: 'POST', body: '{}' }),
  // --- Sales Hub ---
  pipeline: () => call<Pipeline>('/pipeline'),
  trays: (p: { client_id?: number; state?: string; limit?: number } = {}) => call<Page<Tray>>(`/trays${q(p)}`),
  tray: (id: number) => call<Tray>(`/trays/${id}`),
  createTray: (p: { client_id: number; intent?: string; budget?: number; build?: boolean; limit?: number }) =>
    call<Tray>('/trays', { method: 'POST', body: JSON.stringify(p) }),
  buildTray: (id: number, p: { intent?: string; budget?: number; limit?: number } = {}) =>
    call<Tray>(`/trays/${id}/build`, { method: 'POST', body: JSON.stringify(p) }),
  trayPiece: (id: number, piece_id: number, remove = false) =>
    call<Tray>(`/trays/${id}/pieces`, { method: 'POST', body: JSON.stringify({ piece_id, remove }) }),
  shareTray: (id: number) => call<{ tray: Tray; token: string; url: string }>(`/trays/${id}/share`, { method: 'POST', body: '{}' }),
  revokeTray: (id: number) => call<Tray>(`/trays/${id}/revoke`, { method: 'POST', body: '{}' }),
  reserveTray: (id: number, piece_id: number) =>
    call<{ tray: Tray; order: Order }>(`/trays/${id}/reserve`, { method: 'POST', body: JSON.stringify({ piece_id }) }),
  closeTray: (id: number) => call<Tray>(`/trays/${id}/close`, { method: 'POST', body: '{}' }),
  // --- the client's phone: no session, the token is the scope ---
  publicTray: (token: string) => callPublic<PublicTray>(`/jawhar/public/tray/${encodeURIComponent(token)}`),
  publicFeedback: (token: string, ref: string, kind: string, question?: string) =>
    callPublic<PublicTray>(`/jawhar/public/tray/${encodeURIComponent(token)}/feedback`, { method: 'POST', body: JSON.stringify({ ref, kind, question }) }),
  publicViewing: (token: string, preferred: string, note: string) =>
    callPublic<PublicTray>(`/jawhar/public/tray/${encodeURIComponent(token)}/viewing`, { method: 'POST', body: JSON.stringify({ preferred, note }) }),
  // --- the counter ---
  counterPiece: (query: string, discount?: number) => call<CounterPiece>(`/counter/piece${q({ q: query, discount })}`),
  counterReadiness: (p: { piece_id?: number; client_id?: number; discount?: number; old_gold_id?: number }) =>
    call<Readiness>(`/counter/readiness${q(p)}`),
  counterCommit: (p: { client_id: number; piece_id: number; discount?: number; journal_id?: number; amount?: number; old_gold_id?: number }) =>
    call<CounterResult>('/counter/commit', { method: 'POST', body: JSON.stringify(p) }),
  cards: (state = 'open') => call<Page<Card>>(`/owner/cards${q({ state })}`),
  // --- the agents ---
  aiStatus: () => call<AiStatus>('/ai/status'),
  aiPause: (paused: boolean) => call<{ paused: boolean }>('/ai/pause', { method: 'POST', body: JSON.stringify({ paused }) }),
  aiAsk: (text: string) => call<AskResult>('/ai/ask', { method: 'POST', body: JSON.stringify({ text }) }),
  aiBrief: (safe = false) => call<Brief>('/ai/brief', { method: 'POST', body: JSON.stringify({ safe }) }),
  aiQueue: (safe = false) => call<{ items: QueueItem[] } & Partial<Refusal>>(`/ai/queue${q({ safe: safe ? 1 : undefined })}`),
  aiChat: (agent: string, messages: { role: string; text: string }[]) =>
    call<ChatReply>('/ai/chat', { method: 'POST', body: JSON.stringify({ agent, messages }) }),
  aiLaylaTray: (p: { client_id: number; intent?: string; budget?: number; limit?: number }) =>
    call<({ tray: Tray; draft: DraftDetail; run: AiRun }) & Partial<Refusal>>('/ai/layla/tray', { method: 'POST', body: JSON.stringify(p) }),
  aiLaylaFollowup: (p: { client_id: number; channel?: string; context?: string }) =>
    call<({ draft: DraftDetail; run: AiRun }) & Partial<Refusal>>('/ai/layla/followup', { method: 'POST', body: JSON.stringify(p) }),
  aiDrafts: (state = 'pending') => call<{ items: Draft[]; count: number }>(`/ai/drafts${q({ state })}`),
  aiDraft: (id: number) => call<DraftDetail>(`/ai/drafts/${id}`),
  aiDraftApprove: (id: number, digest: string) => call<DraftDetail>(`/ai/drafts/${id}/approve`, { method: 'POST', body: JSON.stringify({ digest }) }),
  aiDraftReturn: (id: number, note?: string) => call<DraftDetail>(`/ai/drafts/${id}/return`, { method: 'POST', body: JSON.stringify({ note }) }),
  aiDraftDismiss: (id: number) => call<DraftDetail>(`/ai/drafts/${id}/dismiss`, { method: 'POST', body: '{}' }),
  aiDraftEdit: (id: number, body: string) => call<DraftDetail>(`/ai/drafts/${id}/edit`, { method: 'POST', body: JSON.stringify({ body }) }),
  aiRuns: () => call<{ items: AiRun[] }>('/ai/runs'),
};
