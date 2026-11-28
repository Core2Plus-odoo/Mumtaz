// Client for the FAIZY ERP (Odoo). The app has no backend of its own:
// every call goes to the same JSON routes the web portal uses
// (faizy_website/controllers/api.py). Auth is Odoo's session cookie.

export type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

export type ApiConfig = { baseUrl: string; db: string; fetchImpl?: FetchLike };

export class ApiError extends Error {
  status: number;
  code: string;
  fields: Record<string, string>;
  constructor(status: number, code: string, fields: Record<string, string> = {}) {
    super(code);
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

export type FamilyMember = {
  id: number; name: string; relationship: string; relationship_label: string | null;
  city: string | null; fmb_id: string;
};
export type OrderSummary = {
  id: number; name: string; title: string; state: string; state_label: string | null;
  is_urgent: boolean; family_member: string | null; created_at: string | null;
};
export type OrderDetail = OrderSummary & {
  service: string; city: string | null; worker_name: string | null; description: string | null;
  proof_image_url: string | null; receipt_image_url: string | null; scheduled_date: string | null;
};
export type Home = {
  partner: { id: number; name: string; first_name: string };
  needs_plan: boolean; family: FamilyMember[]; open_count: number; order_count: number;
  recent_orders: OrderSummary[];
  wa_new_task: string | null; wa_add_member: string | null; wa_change_plan: string | null;
};
export type Service = { id: number; name: string; description: string | null };
export type Category = { id: number; name: string; services: Service[] };
export type RequestOptions = { needs_plan: boolean; categories: Category[]; family: FamilyMember[] };
export type NewRequest = {
  service_id: number; family_member_id?: number; city: string; description: string;
  scheduled_date?: string; urgent?: boolean; privacy_mode?: boolean; client_request_id: string;
};
export type SignUp = { name: string; phone: string; email: string; password: string; country_code?: string };

export function createApi(config: ApiConfig) {
  const doFetch: FetchLike = config.fetchImpl ?? ((url, init) => fetch(url, init));
  const base = config.baseUrl.replace(/\/+$/, "");

  async function call<T>(path: string, body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await doFetch(base + path, {
        method: body === undefined ? "GET" : "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        credentials: "include",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, "network");
    }
    const text = await response.text();
    let data: any = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = null; }
    if (!response.ok || data === null) {
      // An expired session answers with a redirect to the HTML login page.
      if (response.ok && data === null) throw new ApiError(401, "signed_out");
      if (data && data.needs_plan) throw new ApiError(402, "needs_plan");
      throw new ApiError(response.status, (data && data.error) || "server", (data && data.errors) || {});
    }
    return data as T;
  }

  return {
    signUp: (values: SignUp) => call<{ ok: true }>("/api/care/signup", values),

    async signIn(email: string, password: string): Promise<void> {
      const data = await call<any>("/web/session/authenticate", {
        jsonrpc: "2.0",
        params: { db: config.db, login: email.trim().toLowerCase(), password },
      });
      if (data.error || !data.result || !data.result.uid) throw new ApiError(401, "bad_login");
    },

    async signOut(): Promise<void> {
      try { await call<any>("/web/session/destroy", { jsonrpc: "2.0", params: {} }); } catch { /* already out */ }
    },

    home: () => call<Home>("/api/care/home"),
    orders: (page = 1) => call<{ orders: OrderSummary[] }>("/api/care/orders?page=" + page),
    order: (id: number) => call<OrderDetail>("/api/care/orders/" + id),
    requestOptions: () => call<RequestOptions>("/api/care/request/options"),
    createRequest: (values: NewRequest) => call<{ ok: true; order: OrderSummary }>("/api/care/request", values),
  };
}

export type Api = ReturnType<typeof createApi>;
