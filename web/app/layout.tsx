import type { Metadata, Viewport } from "next";

import { BottomNav } from "@/components/shared/BottomNav";
import { Providers } from "@/app/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "FINN",
  description: "What changed in your portfolio, and what it means.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "FINN",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#11161f",
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        {/* Loaded by link rather than next/font so the build never depends on
            reaching Google. Preconnect keeps the runtime cost the same. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=Inter+Tight:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Providers>
          <main className="mx-auto w-full max-w-[560px]">{children}</main>
          <BottomNav />
        </Providers>
      </body>
    </html>
  );
}
