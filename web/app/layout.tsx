import type { Metadata, Viewport } from "next";
import { Inter_Tight, Newsreader } from "next/font/google";

import { BottomNav } from "@/components/shared/BottomNav";
import { Providers } from "@/app/providers";
import "./globals.css";

/* Two families, clearly distinct in role: the serif carries company names and
   every financial figure (tabular lining numerals), the sans carries chrome. */
const serif = Newsreader({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-serif",
  display: "swap",
});

const sans = Inter_Tight({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FINN",
  description: "What changed in your portfolio, and what it means.",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "FINN" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#11161f",
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable}`}>
      <body>
        <Providers>
          <main className="mx-auto w-full max-w-[560px]">{children}</main>
          <BottomNav />
        </Providers>
      </body>
    </html>
  );
}
