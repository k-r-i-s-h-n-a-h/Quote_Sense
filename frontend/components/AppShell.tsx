"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import SiteHeader from "@/components/SiteHeader";
import WelcomeNameModal from "@/components/WelcomeNameModal";
import Footer from "@/components/Footer";
import { userNeedsName } from "@/lib/user-display";

function ShellContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const { isAuthenticated, isLoading, user, fromPmSso } = useAuth();

  const isAuthRoute = pathname === "/login" || pathname === "/register";
  const showNameOnboarding =
    isAuthenticated &&
    !isLoading &&
    !isAuthRoute &&
    !fromPmSso &&
    userNeedsName(user);
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
      <div className="flex flex-col min-h-screen qs-page">
        <div className="flex-1 flex flex-col items-center justify-center gap-3">
          <div
            className="w-8 h-8 border-2 border-stone-200 border-t-[var(--accent)] rounded-full animate-spin"
            aria-hidden
          />
          <p className="text-sm text-stone-500">
            {isLoading ? "Loading QuoteSense…" : "Redirecting to login…"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen qs-page">
      <SiteHeader />
      <div className="flex-1">{children}</div>
      {showFooter && <Footer />}
      {showNameOnboarding && <WelcomeNameModal />}
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
