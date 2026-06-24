"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, isAuthed, type Me } from "@/lib/api";

export function NavAuth() {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);

  // Re-check on every navigation — the layout never remounts, so a one-time
  // mount check would miss the login → redirect transition.
  useEffect(() => {
    if (!isAuthed()) {
      setMe(null);
      setChecked(true);
      return;
    }
    api
      .me()
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setChecked(true));
  }, [pathname]);

  async function onLogout() {
    await api.logout();
    setMe(null);
    router.push("/login");
  }

  if (!checked) return <span className="ml-auto text-sm text-slate-300">…</span>;

  if (!me) {
    return (
      <div className="ml-auto flex items-center gap-3 text-sm">
        <Link href="/login" className="text-slate-300 hover:text-brand">Sign in</Link>
        <Link href="/signup" className="rounded-md bg-brand px-3 py-1 font-medium text-white hover:bg-brand-dark">
          Sign up
        </Link>
      </div>
    );
  }

  return (
    <div className="ml-auto flex items-center gap-3 text-sm">
      <div className="text-right leading-tight">
        <div className="font-medium text-slate-100">{me.organization_name}</div>
        <div className="text-xs text-slate-400">
          {me.full_name || me.email} · {me.role}
          {!me.email_verified && <span className="ml-1 text-amber-600">· unverified</span>}
        </div>
      </div>
      <button onClick={onLogout} className="rounded-md border border-white/15 px-2.5 py-1 text-slate-300 hover:border-brand">
        Sign out
      </button>
    </div>
  );
}
