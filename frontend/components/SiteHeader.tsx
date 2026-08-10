"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import TatvaLogo from "./TatvaLogo";
import ProfileModal from "./ProfileModal";
import TatvaEcosystemMenu from "./TatvaEcosystemMenu";
import { useAuth } from "@/lib/auth";
import { getUserDisplayName, getUserInitial } from "@/lib/user-display";

function NavLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`hidden sm:inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-150 ${
        active
          ? "bg-stone-100 text-stone-900"
          : "text-stone-500 hover:text-stone-900 hover:bg-stone-50"
      }`}
    >
      {children}
    </Link>
  );
}

export default function SiteHeader() {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [profileOpen, setProfileOpen] = useState(false);

  const isAuthRoute = pathname === "/login" || pathname === "/register";
  const displayName = getUserDisplayName(user, "Account");
  const avatarInitial = getUserInitial(user);

  const onProjects =
    pathname === "/" || pathname.startsWith("/project/");
  const onCompare = pathname.startsWith("/compare");

  return (
    <>
      <header className="sticky top-0 z-50 border-b border-stone-200/80 bg-white/90 backdrop-blur-md">
        <div className="qs-container h-14 md:h-16 flex items-center justify-between gap-3">
          <div className="flex items-center gap-4 min-w-0">
            <Link href="/" className="flex items-center gap-2.5 shrink-0 group">
              <TatvaLogo size="sm" />
              <span className="hidden md:flex flex-col leading-tight border-l border-stone-200 pl-2.5">
                <span className="text-[11px] font-semibold tracking-[0.08em] uppercase text-stone-400 group-hover:text-stone-500 transition-colors">
                  TatvaOps
                </span>
                <span className="text-sm font-semibold text-stone-900 tracking-tight">
                  QuoteSense
                </span>
              </span>
            </Link>

            {isAuthenticated && !isAuthRoute && (
              <nav className="flex items-center gap-0.5" aria-label="Primary">
                <NavLink href="/" active={onProjects}>
                  Projects
                </NavLink>
                <NavLink href="/compare" active={onCompare}>
                  Compare
                </NavLink>
              </nav>
            )}
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <TatvaEcosystemMenu />
            {isLoading ? (
              <div className="w-24 h-9 bg-stone-100 rounded-lg qs-skeleton" />
            ) : isAuthenticated ? (
              <div className="flex items-center gap-1.5 sm:gap-2">
                <button
                  type="button"
                  onClick={() => setProfileOpen(true)}
                  aria-label={`Profile — ${displayName}`}
                  className="inline-flex items-center gap-2 rounded-full p-0.5 pr-2 hover:bg-stone-50 transition-colors duration-150"
                >
                  <span className="w-8 h-8 rounded-full bg-stone-800 flex items-center justify-center text-white text-sm font-semibold">
                    {avatarInitial}
                  </span>
                  <span className="hidden lg:inline text-sm font-medium text-stone-700 max-w-[9rem] truncate">
                    {displayName}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    logout();
                    router.push("/login");
                  }}
                  className="qs-btn qs-btn-ghost !py-2 !px-2.5 text-xs sm:text-sm"
                >
                  Sign out
                </button>
              </div>
            ) : isAuthRoute ? null : (
              <div className="flex items-center gap-2">
                <Link href="/login" className="qs-btn qs-btn-secondary !py-2">
                  Sign in
                </Link>
                <Link href="/register" className="qs-btn qs-btn-primary !py-2">
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
