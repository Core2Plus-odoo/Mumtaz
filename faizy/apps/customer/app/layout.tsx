import type { Metadata, Viewport } from "next";
import { Poppins, Noto_Nastaliq_Urdu } from "next/font/google";
import "./globals.css";

/**
 * Poppins is the brand face. Loading only the four weights actually used keeps
 * the payload small — this app is opened on mid-range phones over GCC mobile
 * data, and every unused weight is dead bytes on first paint.
 */
const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-poppins",
  display: "swap",
});

/**
 * Noto Nastaliq Urdu, for Urdu content only. Nastaliq is a genuinely different
 * script style from the Naskh most Arabic fonts ship — falling back to a generic
 * serif renders Urdu in a form that reads as wrong to a native speaker.
 *
 * `preload: false` because most sessions never render Urdu; it loads on demand.
 */
const notoNastaliq = Noto_Nastaliq_Urdu({
  subsets: ["arabic"],
  weight: ["400", "600"],
  variable: "--font-noto-nastaliq",
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  title: "Faizy — حاضر ہیں۔",
  description:
    "Care for your family back home, from anywhere in the Gulf. Groceries, medicine, doctor visits and more — run by vetted Faizies on the ground in Pakistan.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "Faizy" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  themeColor: "#F69E22",
  width: "device-width",
  initialScale: 1,
  // Installed PWA on a phone: fill the display cutout area rather than letterbox.
  viewportFit: "cover",
  // NOT disabling user scaling — pinch-zoom is an accessibility requirement, and
  // a chunk of this audience are older family members reading small text.
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${poppins.variable} ${notoNastaliq.variable}`}>
      <body className="min-h-dvh bg-surface font-sans text-content antialiased">{children}</body>
    </html>
  );
}
