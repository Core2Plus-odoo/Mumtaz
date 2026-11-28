// End-to-end check of the app's API client against a running FAIZY ERP.
//   API_BASE=http://127.0.0.1:8079 ODOO_DB=fw_appdev node scripts/api-smoke.ts
// Uses synthetic data only. Never point this at production.
import { ApiError, createApi } from "../src/api.ts";

const base = process.env.API_BASE ?? "http://127.0.0.1:8079";
const db = process.env.ODOO_DB ?? "faizy";
if (!/^http:\/\/(127\.0\.0\.1|localhost)[:/]/.test(base) && process.env.ALLOW_REMOTE !== "staging") {
  throw new Error("Refusing to run against " + base + " (local only; set ALLOW_REMOTE=staging for a staging copy).");
}

// Node's fetch keeps no cookies, so this stands in for the phone's cookie store.
const jar = new Map<string, string>();
const cookieFetch = async (url: string, init: RequestInit = {}) => {
  const headers = new Headers(init.headers);
  if (jar.size) headers.set("Cookie", [...jar].map(([k, v]) => k + "=" + v).join("; "));
  const response = await fetch(url, { ...init, headers, redirect: "manual" });
  for (const cookie of response.headers.getSetCookie()) {
    const [pair] = cookie.split(";");
    const at = pair.indexOf("=");
    jar.set(pair.slice(0, at), pair.slice(at + 1));
  }
  return response;
};

const api = createApi({ baseUrl: base, db, fetchImpl: cookieFetch });
const stamp = Date.now().toString(36);
const account = {
  name: "SYNTHETIC Smoke " + stamp,
  phone: "+9715" + String(Date.now()).slice(-8),
  email: "synthetic.smoke." + stamp + "@example.com",
  password: "synthetic-" + stamp,
  country_code: "AE",
};
let failed = 0;
const check = (label: string, ok: boolean, extra = "") => {
  if (!ok) failed += 1;
  console.log((ok ? "PASS " : "FAIL ") + label + (extra ? "  " + extra : ""));
};
const code = async (work: () => Promise<unknown>) => {
  try { await work(); return "ok"; } catch (e) { return e instanceof ApiError ? e.code : String(e); }
};

check("home before sign-in is refused", (await code(() => api.home())) !== "ok");
check("sign-up", (await code(() => api.signUp(account))) === "ok");
check("second sign-up with same details is refused", (await code(() => api.signUp(account))) === "already_registered");
check("wrong password is refused", (await code(() => api.signIn(account.email, "wrong-password"))) === "bad_login");
check("sign-in", (await code(() => api.signIn(account.email, account.password))) === "ok");
const home = await api.home();
check("home shows the new customer", home.partner.name === account.name, home.partner.name);
const options = await api.requestOptions();
const service = options.categories[0]?.services[0];
check("request options list services", Boolean(service), service?.name);
if (options.needs_plan) {
  check("plan gate answers needs_plan", (await code(() => api.createRequest({
    service_id: service.id, city: "Karachi", description: "SYNTHETIC smoke", client_request_id: stamp,
  }))) === "needs_plan");
} else {
  const made = await api.createRequest({
    service_id: service.id, city: "Karachi", description: "SYNTHETIC smoke request", client_request_id: stamp,
  });
  check("request created in the ERP", made.ok && made.order.id > 0, made.order.name);
  const again = await api.createRequest({
    service_id: service.id, city: "Karachi", description: "SYNTHETIC smoke request", client_request_id: stamp,
  });
  check("same request sent twice makes one order", again.order.id === made.order.id);
  const list = await api.orders();
  check("request appears in My requests", list.orders.some((o) => o.id === made.order.id));
  const detail = await api.order(made.order.id);
  check("request detail opens", detail.id === made.order.id, detail.state_label ?? "");
  check("unreviewed evidence is not exposed", detail.proof_image_url === null && detail.receipt_image_url === null);
}
await api.signOut();
check("home after sign-out is refused", (await code(() => api.home())) !== "ok");
console.log(failed ? failed + " check(s) failed" : "all checks passed");
process.exit(failed ? 1 : 0);
