"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, isAuthed, type Me } from "@/lib/api";

const APP_LINKS = [
  ["/dashboard", "Dashboard"],
  ["/referrals", "Referrals"],
  ["/review", "Review"],
  ["/tasks", "Tasks"],
  ["/providers", "Providers"],
  ["/workflows", "Workflows"],
] as const;

const MARKETING_LINKS = [
  ["#features", "Features"],
  ["#how", "How it works"],
  ["#workflow", "Workflow builder"],
] as const;

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2">
      <span className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-teal-500 to-emerald-500 text-white shadow-soft">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 12h4l2 5 4-12 2 7h6" />
        </svg>
      </span>
      <span className="font-display text-lg font-extrabold text-ink">FlowCare<span className="text-brand"> AI</span></span>
    </Link>
  );
}

export function SiteNav() {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null | undefined>(undefined);

  useEffect(() => {
    if (!isAuthed()) {
      setMe(null);
      return;
    }
    api.me().then(setMe).catch(() => setMe(null));
  }, [pathname]);

  async function logout() {
    await api.logout();
    setMe(null);
    router.push("/login");
  }

  const authed = !!me;
  const links = authed ? APP_LINKS : MARKETING_LINKS;

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-white/80 backdrop-blur">
      <nav className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-6">
        <Logo />
        <div className="hidden items-center gap-6 md:flex">
          {links.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              className={`text-sm font-medium transition hover:text-brand ${
                pathname === href ? "text-brand" : "text-slate-600"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-3">
          {me === undefined ? (
            <span className="h-4 w-20 animate-pulse rounded bg-slate-100" />
          ) : authed ? (
            <>
              <div className="hidden text-right leading-tight sm:block">
                <div className="text-sm font-semibold text-ink">{me!.organization_name}</div>
                <div className="text-xs text-slate-400">{me!.email}</div>
              </div>
              <button onClick={logout} className="btn-ghost px-4 py-1.5 text-xs">Sign out</button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm font-semibold text-slate-600 hover:text-brand">Sign in</Link>
              <Link href="/signup" className="btn-primary px-4 py-1.5">Get started</Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
