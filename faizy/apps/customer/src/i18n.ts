// Three languages. Urdu wording is a draft pending Mashood's review.
export type Lang = "en" | "ur" | "ro";

const en = {
  tagline: "Simplifying Life Across Borders.",
  welcome: "Welcome to FAIZY", createAccount: "Create your account", fullName: "Full name",
  whatsapp: "WhatsApp number", email: "Email", password: "Password", signIn: "Sign in",
  createBtn: "Create account", newHere: "New here? Create an account",
  haveAccount: "Already have an account? Sign in", hello: "Hello,",
  homeTitle: "What do you need done?", talk: "Talk to FAIZY", newRequest: "New request",
  myRequests: "My requests", family: "Family", addFamily: "Add a family member",
  help: "Help on WhatsApp", home: "Home", requests: "Requests", signOut: "Sign out",
  noRequests: "No requests yet.", noFamily: "No family members yet.",
  addFamilyNote: "The FAIZY team will ask you for the details on WhatsApp.",
  service: "Service", forWhom: "For", city: "City in Pakistan", details: "Details",
  urgent: "Urgent", review: "Review request", send: "Send request", back: "Back",
  sendNote: "Nothing is sent until you tap Send request. Our team replies between 10am and 9pm, Karachi time.",
  sent: "Your request has been sent.", helper: "Your FAIZY helper", proof: "Proof (photo)",
  receipt: "Receipt", checking: "Being checked by FAIZY before you see it.",
  planTitle: "You need a plan before sending requests",
  planBody: "The FAIZY team will confirm the plan and its price with you on WhatsApp.",
  askPlan: "Ask about a plan on WhatsApp",
  talkSoon: "The speaking assistant is not switched on yet. Use New request for now.",
  aiLabel: "FAIZY AI assistant, not a person", loading: "Loading…", me: "Me",
  err_network: "Cannot reach FAIZY. Check your internet and try again.",
  err_bad_login: "Email or password is not correct.",
  err_already_registered: "This email or number is already registered. Sign in, or message us on WhatsApp.",
  err_signup_closed: "Sign-up in the app is not open yet. Please message us on WhatsApp.",
  err_too_many_attempts: "Too many tries. Please wait an hour and try again.",
  err_signed_out: "Please sign in again.", err_server: "Something went wrong. Please try again.",
  err_fields: "Please check the highlighted details.", err_required: "Please fill in every field.",
};
export type Strings = typeof en;

const ur: Strings = {
  ...en,
  welcome: "فیضی میں خوش آمدید", createAccount: "اپنا اکاؤنٹ بنائیں", fullName: "پورا نام",
  whatsapp: "واٹس ایپ نمبر", email: "ای میل", password: "پاس ورڈ", signIn: "سائن ان کریں",
  createBtn: "اکاؤنٹ بنائیں", newHere: "نئے ہیں؟ اکاؤنٹ بنائیں",
  haveAccount: "پہلے سے اکاؤنٹ ہے؟ سائن ان کریں", hello: "السلام علیکم،",
  homeTitle: "آپ کو کیا کام کروانا ہے؟", talk: "فیضی سے بات کریں", newRequest: "نئی ریکویسٹ",
  myRequests: "میری ریکویسٹس", family: "فیملی", addFamily: "فیملی ممبر شامل کریں",
  help: "واٹس ایپ پر مدد", home: "ہوم", requests: "ریکویسٹس", signOut: "سائن آؤٹ",
  noRequests: "ابھی کوئی ریکویسٹ نہیں۔", noFamily: "ابھی کوئی فیملی ممبر نہیں۔",
  addFamilyNote: "فیضی ٹیم واٹس ایپ پر آپ سے تفصیل لے گی۔",
  service: "سروس", forWhom: "کس کے لیے", city: "پاکستان میں شہر", details: "تفصیل",
  urgent: "فوری", review: "ریکویسٹ دیکھیں", send: "ریکویسٹ بھیجیں", back: "واپس",
  sendNote: "جب تک آپ ریکویسٹ بھیجیں پر ٹیپ نہیں کرتے، کچھ نہیں بھیجا جاتا۔ ہماری ٹیم صبح 10 سے رات 9 بجے تک (کراچی وقت) جواب دیتی ہے۔",
  sent: "آپ کی ریکویسٹ بھیج دی گئی ہے۔", helper: "آپ کا فیضی ہیلپر", proof: "ثبوت (تصویر)",
  receipt: "رسید", checking: "آپ کو دکھانے سے پہلے فیضی چیک کر رہی ہے۔",
  planTitle: "ریکویسٹ بھیجنے سے پہلے پلان چاہیے",
  planBody: "فیضی ٹیم پلان اور اس کی قیمت واٹس ایپ پر آپ سے کنفرم کرے گی۔",
  askPlan: "واٹس ایپ پر پلان پوچھیں",
  talkSoon: "بولنے والا اسسٹنٹ ابھی چالو نہیں۔ فی الحال نئی ریکویسٹ استعمال کریں۔",
  aiLabel: "فیضی اے آئی اسسٹنٹ، انسان نہیں", loading: "لوڈ ہو رہا ہے…", me: "میں خود",
  err_network: "فیضی سے رابطہ نہیں ہو رہا۔ انٹرنیٹ چیک کر کے دوبارہ کوشش کریں۔",
  err_bad_login: "ای میل یا پاس ورڈ درست نہیں۔",
  err_already_registered: "یہ ای میل یا نمبر پہلے سے رجسٹرڈ ہے۔ سائن ان کریں یا واٹس ایپ پر رابطہ کریں۔",
  err_signup_closed: "ایپ میں سائن اپ ابھی کھلا نہیں۔ براہ کرم واٹس ایپ پر رابطہ کریں۔",
  err_too_many_attempts: "بہت زیادہ کوششیں۔ ایک گھنٹے بعد دوبارہ کوشش کریں۔",
  err_signed_out: "براہ کرم دوبارہ سائن ان کریں۔", err_server: "کچھ غلط ہو گیا۔ دوبارہ کوشش کریں۔",
  err_fields: "براہ کرم نشان زدہ تفصیل چیک کریں۔", err_required: "براہ کرم ہر خانہ بھریں۔",
};

const ro: Strings = {
  ...en,
  welcome: "FAIZY mein khush aamdeed", createAccount: "Apna account banayein", fullName: "Poora naam",
  signIn: "Sign in karein", createBtn: "Account banayein", newHere: "Naye hain? Account banayein",
  haveAccount: "Pehle se account hai? Sign in karein", hello: "Assalam o Alaikum,",
  homeTitle: "Aap ko kya kaam karwana hai?", talk: "FAIZY se baat karein", newRequest: "Nayi request",
  myRequests: "Meri requests", addFamily: "Family member add karein", help: "WhatsApp par madad",
  noRequests: "Abhi koi request nahi.", noFamily: "Abhi koi family member nahi.",
  addFamilyNote: "FAIZY team WhatsApp par aap se details legi.",
  forWhom: "Kis ke liye", city: "Pakistan mein shehar", details: "Tafseel", urgent: "Urgent (zaroori)",
  review: "Request dekhein", send: "Request bhejein", back: "Wapas",
  sendNote: "Jab tak aap Request bhejein par tap nahi karte, kuch nahi bheja jata. Hamari team subah 10 se raat 9 baje tak (Karachi time) jawab deti hai.",
  sent: "Aap ki request bhej di gayi hai.", helper: "Aap ka FAIZY helper", proof: "Saboot (photo)",
  checking: "Aap ko dikhane se pehle FAIZY check kar rahi hai.",
  planTitle: "Request bhejne se pehle plan chahiye",
  planBody: "FAIZY team plan aur uski qeemat WhatsApp par confirm karegi.",
  askPlan: "WhatsApp par plan poochein",
  talkSoon: "Bolne wala assistant abhi chalu nahi. Filhal Nayi request istemal karein.",
  aiLabel: "FAIZY AI assistant, insaan nahi", loading: "Load ho raha hai…", me: "Main khud",
  err_network: "FAIZY se rabta nahi ho raha. Internet check karke dobara koshish karein.",
  err_bad_login: "Email ya password theek nahi.",
  err_already_registered: "Yeh email ya number pehle se registered hai. Sign in karein ya WhatsApp par rabta karein.",
  err_signup_closed: "App mein sign-up abhi khula nahi. WhatsApp par rabta karein.",
  err_too_many_attempts: "Bohat zyada koshishein. Ek ghante baad dobara koshish karein.",
  err_signed_out: "Dobara sign in karein.", err_server: "Kuch ghalat ho gaya. Dobara koshish karein.",
  err_fields: "Nishan zada details check karein.", err_required: "Har khana bharein.",
};

export const strings: Record<Lang, Strings> = { en, ur, ro };
export const isRtl = (lang: Lang) => lang === "ur";
export function errorText(t: Strings, code: string): string {
  const key = ("err_" + code) as keyof Strings;
  return (t[key] as string) ?? t.err_server;
}
