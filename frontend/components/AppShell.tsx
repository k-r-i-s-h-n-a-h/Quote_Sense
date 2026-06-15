"use client";

import { AuthProvider } from "@/lib/auth";
import SiteHeader from "@/components/SiteHeader";
import Footer from "@/components/Footer";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <div className="flex flex-col min-h-screen">
        <SiteHeader />
        <div className="flex-1">{children}</div>
        <Footer />
      </div>
    </AuthProvider>
  );
}
