"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import TatvaLogo from "./TatvaLogo";
import ProfileModal from "./ProfileModal";
import TatvaEcosystemMenu from "./TatvaEcosystemMenu";
import { useAuth } from "@/lib/auth";
import { getUserDisplayName, getUserInitial } from "@/lib/user-display";

export default function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [profileOpen, setProfileOpen] = useState(false);

  const isAuthRoute = pathname === "/login" || pathname === "/register";

  const displayName = getUserDisplayName(user, "Account");
  const avatarInitial = getUserInitial(user);

  return (
    <>
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 shrink-0">
            <TatvaLogo size="sm" />
          </Link>

          <div className="flex items-center gap-3">
            <TatvaEcosystemMenu />
            {isLoading ? (
              <div className="w-24 h-9 bg-slate-100 rounded-lg animate-pulse" />
            ) : isAuthenticated ? (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setProfileOpen(true)}
                  aria-label={`Profile — ${displayName}`}
                  className="inline-flex items-center justify-center w-9 h-9 rounded-full hover:bg-slate-50 transition-colors"
                >
                  <span className="w-8 h-8 rounded-full bg-gradient-to-br from-slate-400 to-slate-600 flex items-center justify-center text-white text-sm font-bold">
                    {avatarInitial}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    logout();
                    router.push("/login");
                  }}
                  className="text-sm text-slate-500 hover:text-red-600 px-2 py-1 transition-colors"
                >
                  Sign out
                </button>
              </div>
            ) : isAuthRoute ? null : (
              <div className="flex items-center gap-2">
                <Link
                  href="/login"
                  className="inline-flex items-center px-4 py-2 text-sm font-medium text-slate-700 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  className="inline-flex items-center px-5 py-2 text-sm font-semibold text-white bg-[#c04a00] rounded-lg hover:bg-[#a84000] transition-colors shadow-sm"
                >
                  Register
                </Link>
              </div>
            )}
          </div>
        </div>
      </header>

      <ProfileModal open={profileOpen} onClose={() => setProfileOpen(false)} />
    </>
  );
}
