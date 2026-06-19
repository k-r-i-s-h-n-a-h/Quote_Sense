"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import SiteHeader from "@/components/SiteHeader";
import Footer from "@/components/Footer";

function ShellContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  const isAuthRoute = pathname === "/login" || pathname === "/register";
  const showFooter = isAuthRoute && !isAuthenticated;
  const isProtectedRoute =
    pathname === "/" || pathname === "/compare" || pathname.startsWith("/project/");

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated && isProtectedRoute) {
      const returnTo = `${window.location.pathname}${window.location.search}`;
      router.replace(`/login?returnTo=${encodeURIComponent(returnTo)}`);
    }
  }, [isLoading, isAuthenticated, isProtectedRoute, router]);

  if (isLoading || (!isAuthenticated && isProtectedRoute)) {
    return (
      <div className="flex flex-col min-h-screen">
        <div className="flex-1 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
      <SiteHeader />
      <div className="flex-1">{children}</div>
      {showFooter && <Footer />}
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ShellContent>{children}</ShellContent>
    </AuthProvider>
  );
}
