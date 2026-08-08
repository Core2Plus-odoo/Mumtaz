import type { Metadata, Viewport } from "next";
import { Poppins, Noto_Nastaliq_Urdu } from "next/font/google";
import "./globals.css";

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-poppins",
  display: "swap",
});

/**
 * Urdu is loaded (not deferred) in the worker app — unlike the customer app,
 * most of these users are in Pakistan and Urdu is the primary interface
 * language, not an occasional tagline.
 */
const notoNastaliq = Noto_Nastaliq_Urdu({
  subsets: ["arabic"],
  weight: ["400", "600"],
  variable: "--font-noto-nastaliq",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Faizy Worker",
  description: "Assigned jobs, photo proof, earnings.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Faizy Work" },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#F69E22",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${poppins.variable} ${notoNastaliq.variable}`}>
      <body className="min-h-dvh bg-surface font-sans text-content antialiased">{children}</body>
    </html>
  );
}
