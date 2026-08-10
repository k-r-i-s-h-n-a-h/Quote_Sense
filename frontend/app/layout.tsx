import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import AppShell from "@/components/AppShell";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "QuoteSense | TatvaOps Procurement Intelligence",
  description:
    "Compare vendor quotes side-by-side with AI-powered insights and a live market baseline — by TatvaOps.",
  icons: {
    icon: "/logo_fevicon.png",
    apple: "/logo_fevicon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${dmSans.variable} antialiased font-sans`}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
