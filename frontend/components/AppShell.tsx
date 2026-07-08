"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import SiteHeader from "@/components/SiteHeader";
import WelcomeNameModal from "@/components/WelcomeNameModal";
import Footer from "@/components/Footer";
import { userNeedsName } from "@/lib/user-display";

function ShellContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuth();

  const isAuthRoute = pathname === "/login" || pathname === "/register";
  const showNameOnboarding =
    isAuthenticated && !isLoading && !isAuthRoute && userNeedsName(user);
  const showFooter = isAuthRoute && !isAuthenticated;
  const isProtectedRoute =
    pathname === "/" || pathname === "/compare" || pathname.startsWith("/project/");

  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7880/ingest/fae56c38-48bc-450d-a803-35ac016bc76b',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'b7c34a'},body:JSON.stringify({sessionId:'b7c34a',location:'AppShell.tsx:state',message:'shell render state',data:{isLoading,isAuthenticated,pathname,isProtectedRoute},timestamp:Date.now(),hypothesisId:'H2'})}).catch(()=>{});
    // #endregion
    if (isLoading) return;
    if (!isAuthenticated && isProtectedRoute) {
      const returnTo = `${window.location.pathname}${window.location.search}`;
      router.replace(`/login?returnTo=${encodeURIComponent(returnTo)}`);
    }
  }, [isLoading, isAuthenticated, isProtectedRoute, router]);

  if (isLoading || (!isAuthenticated && isProtectedRoute)) {
    return (
      <div className="flex flex-col min-h-screen bg-[#f8fafc]">
        <div className="flex-1 flex flex-col items-center justify-center gap-3">
          <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
          <p className="text-sm text-slate-500">
            {isLoading ? "Loading QuoteSense…" : "Redirecting to login…"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
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
