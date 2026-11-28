import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator, Image, Linking, Pressable, SafeAreaView, ScrollView, StyleSheet, Switch,
  Text, TextInput, View,
} from "react-native";

import {
  ApiError, createApi, Category, FamilyMember, Home, OrderDetail, OrderSummary, Service,
} from "./src/api";
import { API_BASE, ODOO_DB } from "./src/config";
import { errorText, isRtl, Lang, strings, Strings } from "./src/i18n";
import { color } from "./src/theme";

type Screen =
  | "signin" | "signup" | "home" | "talk" | "new" | "review" | "sent" | "plan"
  | "requests" | "detail" | "family";

type Draft = {
  service: Service | null; member: FamilyMember | null; city: string; description: string;
  urgent: boolean; requestId: string;
};

const emptyDraft = (): Draft => ({
  service: null, member: null, city: "", description: "", urgent: false,
  requestId: Date.now().toString(36) + Math.random().toString(36).slice(2, 10),
});

const logo = require("./assets/faizy-logo.png");

export default function App() {
  const api = useMemo(() => createApi({ baseUrl: API_BASE, db: ODOO_DB }), []);
  const [lang, setLang] = useState<Lang>("en");
  const t = strings[lang];
  const rtl = isRtl(lang);
  const [screen, setScreen] = useState<Screen>("signin");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [home, setHome] = useState<Home | null>(null);
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [detail, setDetail] = useState<OrderDetail | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [form, setForm] = useState({ name: "", phone: "", email: "", password: "" });

  const go = useCallback((next: Screen) => { setError(""); setScreen(next); }, []);

  // One place turns a failed call into a message or a change of screen.
  const run = useCallback(async (work: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(0, "server");
      if (err.code === "signed_out") { setHome(null); setScreen("signin"); }
      else if (err.code === "needs_plan") { setScreen("plan"); return; }
      setError(Object.keys(err.fields).length ? t.err_fields : errorText(t, err.code));
    } finally {
      setBusy(false);
    }
  }, [t]);

  const loadHome = useCallback(() => run(async () => {
    setHome(await api.home());
    setScreen("home");
  }), [api, run]);

  const signIn = () => run(async () => {
    if (!form.email || !form.password) throw new ApiError(400, "required");
    await api.signIn(form.email, form.password);
    setHome(await api.home());
    setForm({ name: "", phone: "", email: "", password: "" });
    setScreen("home");
  });

  const signUp = () => run(async () => {
    if (!form.name || !form.phone || !form.email || !form.password) throw new ApiError(400, "required");
    await api.signUp(form);
    await api.signIn(form.email, form.password);
    setHome(await api.home());
    setForm({ name: "", phone: "", email: "", password: "" });
    setScreen("home");
  });

  const signOut = () => run(async () => { await api.signOut(); setHome(null); setScreen("signin"); });

  const openRequests = () => run(async () => {
    setOrders((await api.orders()).orders);
    setScreen("requests");
  });

  const openDetail = (id: number) => run(async () => {
    setDetail(await api.order(id));
    setScreen("detail");
  });

  const openNew = () => run(async () => {
    const options = await api.requestOptions();
    if (options.needs_plan) { setScreen("plan"); return; }
    setCategories(options.categories);
    setDraft(emptyDraft());
    setScreen("new");
  });

  const openFamily = () => run(async () => { setHome(await api.home()); setScreen("family"); });

  const review = () => {
    if (!draft.service || !draft.city.trim() || !draft.description.trim()) { setError(t.err_required); return; }
    go("review");
  };

  // The only place a request is created, and only from the customer's tap.
  const send = () => run(async () => {
    if (!draft.service) return;
    await api.createRequest({
      service_id: draft.service.id,
      family_member_id: draft.member ? draft.member.id : undefined,
      city: draft.city.trim(),
      description: draft.description.trim(),
      urgent: draft.urgent,
      client_request_id: draft.requestId,
    });
    setScreen("sent");
  });

  const whatsapp = (url: string | null | undefined) => { if (url) Linking.openURL(url).catch(() => {}); };

  useEffect(() => { /* a saved session, if any, is tried once on start */
    api.home().then((h) => { setHome(h); setScreen("home"); }).catch(() => {});
  }, [api]);

  const align = { textAlign: rtl ? ("right" as const) : ("left" as const), writingDirection: rtl ? ("rtl" as const) : ("ltr" as const) };
  const tabs = screen === "home" || screen === "requests" || screen === "family";

  return (
    <SafeAreaView style={s.root}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={s.body} keyboardShouldPersistTaps="handled">
        {(screen === "signin" || screen === "signup") && (
          <View style={s.gap}>
            <View style={s.center}>
              <Image source={logo} style={s.logoBig} accessibilityLabel="FAIZY logo" />
              <Text style={s.h1}>{screen === "signin" ? t.welcome : t.createAccount}</Text>
              <Text style={s.muted}>{t.tagline}</Text>
            </View>
            <LangSwitch lang={lang} onChange={setLang} />
            {screen === "signup" && (
              <>
                <Field label={t.fullName} value={form.name} onChange={(name) => setForm({ ...form, name })} align={align} />
                <Field label={t.whatsapp} value={form.phone} onChange={(phone) => setForm({ ...form, phone })} keyboard="phone-pad" align={align} />
              </>
            )}
            <Field label={t.email} value={form.email} onChange={(email) => setForm({ ...form, email })} keyboard="email-address" align={align} />
            <Field label={t.password} value={form.password} onChange={(password) => setForm({ ...form, password })} secure align={align} />
            <Notice text={error} />
            <Btn label={screen === "signin" ? t.signIn : t.createBtn} onPress={screen === "signin" ? signIn : signUp} busy={busy} />
            <LinkBtn label={screen === "signin" ? t.newHere : t.haveAccount} onPress={() => go(screen === "signin" ? "signup" : "signin")} />
          </View>
        )}

        {screen === "home" && home && (
          <View style={s.gap}>
            <View style={[s.row, rtl && s.rowRtl]}>
              <Image source={logo} style={s.logoSmall} accessibilityLabel="FAIZY logo" />
              <View style={s.flex}>
                <Text style={[s.muted, align]}>{t.hello}</Text>
                <Text style={[s.h2, align]}>{home.partner.first_name}</Text>
              </View>
            </View>
            <LangSwitch lang={lang} onChange={setLang} />
            <Text style={[s.h1, s.centerText]}>{t.homeTitle}</Text>
            <Pressable accessibilityRole="button" accessibilityLabel={t.talk} onPress={() => go("talk")} style={s.talk}>
              <Text style={s.talkText}>{t.talk}</Text>
            </Pressable>
            <Notice text={error} />
            <View style={s.grid}>
              <Tile label={t.newRequest} onPress={openNew} />
              <Tile label={`${t.myRequests} (${home.open_count})`} onPress={openRequests} />
              <Tile label={t.family} onPress={openFamily} />
              <Tile label={t.help} onPress={() => whatsapp(home.wa_new_task)} />
            </View>
            <LinkBtn label={t.signOut} onPress={signOut} />
          </View>
        )}

        {screen === "talk" && (
          <View style={[s.gap, s.center]}>
            <Text style={s.muted}>{t.aiLabel}</Text>
            <Image source={logo} style={s.logoBig} accessibilityLabel="FAIZY logo" />
            <Text style={[s.body16, s.centerText]}>{t.talkSoon}</Text>
            <Btn label={t.newRequest} onPress={openNew} busy={busy} />
            <LinkBtn label={t.back} onPress={() => go("home")} />
          </View>
        )}

        {screen === "new" && (
          <View style={s.gap}>
            <Text style={[s.h1, align]}>{t.newRequest}</Text>
            <Text style={[s.label, align]}>{t.service}</Text>
            {categories.map((category) => (
              <View key={category.id} style={s.gapSmall}>
                <Text style={[s.muted, align]}>{category.name}</Text>
                <View style={[s.wrap, rtl && s.rowRtl]}>
                  {category.services.map((service) => (
                    <Chip key={service.id} label={service.name} on={draft.service?.id === service.id} onPress={() => setDraft({ ...draft, service })} />
                  ))}
                </View>
              </View>
            ))}
            <Text style={[s.label, align]}>{t.forWhom}</Text>
            <View style={[s.wrap, rtl && s.rowRtl]}>
              <Chip label={t.me} on={!draft.member} onPress={() => setDraft({ ...draft, member: null })} />
              {(home?.family ?? []).map((member) => (
                <Chip key={member.id} label={member.name} on={draft.member?.id === member.id}
                  onPress={() => setDraft({ ...draft, member, city: draft.city || member.city || "" })} />
              ))}
            </View>
            <Field label={t.city} value={draft.city} onChange={(city) => setDraft({ ...draft, city })} align={align} />
            <Field label={t.details} value={draft.description} onChange={(description) => setDraft({ ...draft, description })} multiline align={align} />
            <View style={[s.row, rtl && s.rowRtl, s.between]}>
              <Text style={s.label}>{t.urgent}</Text>
              <Switch value={draft.urgent} onValueChange={(urgent) => setDraft({ ...draft, urgent })} trackColor={{ true: color.navy, false: color.line }} />
            </View>
            <Notice text={error} />
            <Btn label={t.review} onPress={review} />
            <LinkBtn label={t.back} onPress={() => go("home")} />
          </View>
        )}

        {screen === "review" && draft.service && (
          <View style={s.gap}>
            <Text style={[s.h1, align]}>{t.review}</Text>
            <Line label={t.service} value={draft.service.name} align={align} />
            <Line label={t.forWhom} value={draft.member ? draft.member.name : t.me} align={align} />
            <Line label={t.city} value={draft.city} align={align} />
            <Line label={t.details} value={draft.description} align={align} />
            {draft.urgent && <Line label={t.urgent} value="✓" align={align} />}
            <Text style={[s.muted, s.centerText]}>{t.sendNote}</Text>
            <Notice text={error} />
            <Btn label={t.send} onPress={send} busy={busy} />
            <LinkBtn label={t.back} onPress={() => go("new")} />
          </View>
        )}

        {screen === "sent" && (
          <View style={[s.gap, s.center]}>
            <Text style={[s.h1, s.centerText]}>{t.sent}</Text>
            <Btn label={t.myRequests} onPress={openRequests} busy={busy} />
            <LinkBtn label={t.home} onPress={loadHome} />
          </View>
        )}

        {screen === "plan" && (
          <View style={[s.gap, s.center]}>
            <Text style={[s.h1, s.centerText]}>{t.planTitle}</Text>
            <Text style={[s.body16, s.centerText]}>{t.planBody}</Text>
            <Btn label={t.askPlan} onPress={() => whatsapp(home?.wa_change_plan)} />
            <LinkBtn label={t.back} onPress={() => go("home")} />
          </View>
        )}

        {screen === "requests" && (
          <View style={s.gap}>
            <Text style={[s.h1, align]}>{t.myRequests}</Text>
            <Notice text={error} />
            {orders.length === 0 && <Text style={[s.muted, align]}>{t.noRequests}</Text>}
            {orders.map((order) => (
              <Pressable key={order.id} accessibilityRole="button" onPress={() => openDetail(order.id)} style={s.card}>
                <Text style={[s.cardTitle, align]}>{order.title || order.name}</Text>
                <Text style={[s.muted, align]}>{[order.family_member, order.state_label].filter(Boolean).join(" · ")}</Text>
              </Pressable>
            ))}
            <Btn label={t.newRequest} onPress={openNew} busy={busy} />
          </View>
        )}

        {screen === "detail" && detail && (
          <View style={s.gap}>
            <Text style={[s.h1, align]}>{detail.title || detail.name}</Text>
            <Text style={[s.muted, align]}>{[detail.service, detail.city].filter(Boolean).join(" · ")}</Text>
            <View style={s.status}><Text style={s.statusText}>{detail.state_label}</Text></View>
            {detail.worker_name && <Line label={t.helper} value={detail.worker_name} align={align} />}
            {detail.description && <Line label={t.details} value={detail.description} align={align} />}
            <Text style={[s.label, align]}>{t.proof}</Text>
            {detail.proof_image_url
              ? <Image source={{ uri: API_BASE + detail.proof_image_url }} style={s.evidence} accessibilityLabel={t.proof} />
              : <Text style={[s.muted, align]}>{t.checking}</Text>}
            <Text style={[s.label, align]}>{t.receipt}</Text>
            {detail.receipt_image_url
              ? <Image source={{ uri: API_BASE + detail.receipt_image_url }} style={s.evidence} accessibilityLabel={t.receipt} />
              : <Text style={[s.muted, align]}>{t.checking}</Text>}
            <Btn label={t.help} onPress={() => whatsapp(home?.wa_new_task)} />
            <LinkBtn label={t.back} onPress={() => go("requests")} />
          </View>
        )}

        {screen === "family" && home && (
          <View style={s.gap}>
            <Text style={[s.h1, align]}>{t.family}</Text>
            {home.family.length === 0 && <Text style={[s.muted, align]}>{t.noFamily}</Text>}
            {home.family.map((member) => (
              <View key={member.id} style={s.card}>
                <Text style={[s.cardTitle, align]}>{member.name}</Text>
                <Text style={[s.muted, align]}>{[member.relationship_label, member.city].filter(Boolean).join(" · ")}</Text>
              </View>
            ))}
            <Btn label={t.addFamily} onPress={() => whatsapp(home.wa_add_member)} />
            <Text style={[s.muted, s.centerText]}>{t.addFamilyNote}</Text>
          </View>
        )}

        {busy && !home && <ActivityIndicator color={color.navy} />}
      </ScrollView>

      {tabs && (
        <View style={[s.tabs, rtl && s.rowRtl]}>
          <Tab label={t.home} on={screen === "home"} onPress={loadHome} />
          <Tab label={t.requests} on={screen === "requests"} onPress={openRequests} />
          <Tab label={t.family} on={screen === "family"} onPress={openFamily} />
        </View>
      )}
    </SafeAreaView>
  );
}

type Align = { textAlign: "left" | "right"; writingDirection: "ltr" | "rtl" };

function Btn({ label, onPress, busy }: { label: string; onPress: () => void; busy?: boolean }) {
  return (
    <Pressable accessibilityRole="button" disabled={busy} onPress={onPress} style={[s.btn, busy && s.dim]}>
      {busy ? <ActivityIndicator color={color.navy} /> : <Text style={s.btnText}>{label}</Text>}
    </Pressable>
  );
}

function LinkBtn({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={s.link}>
      <Text style={s.linkText}>{label}</Text>
    </Pressable>
  );
}

function Tile({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={s.tile}>
      <Text style={s.tileText}>{label}</Text>
    </Pressable>
  );
}

function Chip({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityState={{ selected: on }} onPress={onPress} style={[s.chip, on && s.chipOn]}>
      <Text style={[s.chipText, on && s.chipTextOn]}>{label}</Text>
    </Pressable>
  );
}

function Tab({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="tab" accessibilityState={{ selected: on }} onPress={onPress} style={[s.tab, on && s.tabOn]}>
      <Text style={[s.tabText, on && s.tabTextOn]}>{label}</Text>
    </Pressable>
  );
}

function Line({ label, value, align }: { label: string; value: string; align: Align }) {
  return (
    <View style={s.line}>
      <Text style={[s.muted, align]}>{label}</Text>
      <Text style={[s.body16, align]}>{value}</Text>
    </View>
  );
}

function Notice({ text }: { text: string }) {
  if (!text) return null;
  return <Text accessibilityRole="alert" style={s.notice}>{text}</Text>;
}

function Field(props: {
  label: string; value: string; onChange: (value: string) => void; align: Align;
  secure?: boolean; multiline?: boolean; keyboard?: "email-address" | "phone-pad";
}) {
  return (
    <View style={s.gapSmall}>
      <Text style={[s.label, props.align]}>{props.label}</Text>
      <TextInput
        accessibilityLabel={props.label}
        value={props.value}
        onChangeText={props.onChange}
        secureTextEntry={props.secure}
        multiline={props.multiline}
        keyboardType={props.keyboard ?? "default"}
        autoCapitalize={props.keyboard || props.secure ? "none" : "sentences"}
        style={[s.input, props.multiline && s.inputTall, props.keyboard || props.secure ? null : props.align]}
      />
    </View>
  );
}

function LangSwitch({ lang, onChange }: { lang: Lang; onChange: (lang: Lang) => void }) {
  const options: [Lang, string][] = [["en", "English"], ["ur", "اردو"], ["ro", "Roman Urdu"]];
  return (
    <View style={s.seg} accessibilityRole="tablist">
      {options.map(([code, label]) => (
        <Pressable key={code} accessibilityRole="tab" accessibilityState={{ selected: lang === code }}
          onPress={() => onChange(code)} style={[s.segItem, lang === code && s.segOn]}>
          <Text style={[s.segText, lang === code && s.segTextOn]}>{label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.white },
  body: { padding: 20, paddingBottom: 32 },
  gap: { gap: 14 },
  gapSmall: { gap: 6 },
  flex: { flex: 1 },
  center: { alignItems: "center", gap: 10 },
  centerText: { textAlign: "center" },
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  rowRtl: { flexDirection: "row-reverse" },
  between: { justifyContent: "space-between" },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  logoBig: { width: 104, height: 104 },
  logoSmall: { width: 52, height: 52 },
  h1: { fontSize: 24, lineHeight: 34, fontWeight: "700", color: color.navy },
  h2: { fontSize: 20, lineHeight: 28, fontWeight: "600", color: color.navy },
  body16: { fontSize: 16, lineHeight: 26, color: color.navy },
  label: { fontSize: 14, fontWeight: "600", color: color.navy },
  muted: { fontSize: 14, lineHeight: 22, color: color.muted },
  input: { minHeight: 52, borderRadius: 14, backgroundColor: color.surface, paddingHorizontal: 16, fontSize: 16, color: color.navy },
  inputTall: { minHeight: 96, paddingTop: 12, textAlignVertical: "top" },
  btn: { minHeight: 56, borderRadius: 999, backgroundColor: color.orange, alignItems: "center", justifyContent: "center", paddingHorizontal: 20 },
  btnText: { fontSize: 16, fontWeight: "700", color: color.navy },
  dim: { opacity: 0.6 },
  link: { minHeight: 44, alignItems: "center", justifyContent: "center" },
  linkText: { fontSize: 14, fontWeight: "600", color: color.navy, textDecorationLine: "underline" },
  talk: { alignSelf: "center", width: 156, height: 156, borderRadius: 78, backgroundColor: color.orange, borderWidth: 10, borderColor: color.orangeSoft, alignItems: "center", justifyContent: "center", padding: 12 },
  talkText: { fontSize: 15, fontWeight: "700", color: color.navy, textAlign: "center" },
  tile: { flexBasis: "47%", flexGrow: 1, minHeight: 76, borderRadius: 16, backgroundColor: color.surface, padding: 14, justifyContent: "center" },
  tileText: { fontSize: 15, fontWeight: "600", color: color.navy },
  chip: { minHeight: 44, paddingHorizontal: 16, borderRadius: 999, backgroundColor: color.surface, justifyContent: "center" },
  chipOn: { backgroundColor: color.navy },
  chipText: { fontSize: 14, fontWeight: "600", color: color.navy },
  chipTextOn: { color: color.white },
  card: { borderWidth: 1, borderColor: color.line, borderRadius: 16, padding: 16, gap: 6 },
  cardTitle: { fontSize: 16, fontWeight: "600", color: color.navy },
  line: { backgroundColor: color.surface, borderRadius: 14, padding: 14, gap: 2 },
  status: { alignSelf: "flex-start", backgroundColor: color.orangeSoft, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 6 },
  statusText: { fontSize: 14, fontWeight: "600", color: color.navy },
  evidence: { width: "100%", height: 200, borderRadius: 16, backgroundColor: color.surface },
  notice: { backgroundColor: color.orangeSoft, color: color.navy, borderRadius: 12, padding: 12, fontSize: 14, lineHeight: 22 },
  seg: { flexDirection: "row", backgroundColor: color.surface, borderRadius: 999, padding: 4 },
  segItem: { flex: 1, minHeight: 44, borderRadius: 999, alignItems: "center", justifyContent: "center" },
  segOn: { backgroundColor: color.navy },
  segText: { fontSize: 14, fontWeight: "600", color: color.navy },
  segTextOn: { color: color.white },
  tabs: { flexDirection: "row", borderTopWidth: 1, borderTopColor: color.line, backgroundColor: color.white },
  tab: { flex: 1, minHeight: 64, alignItems: "center", justifyContent: "center", borderTopWidth: 3, borderTopColor: color.white },
  tabOn: { borderTopColor: color.orange },
  tabText: { fontSize: 13, fontWeight: "500", color: color.muted },
  tabTextOn: { fontWeight: "700", color: color.navy },
});
