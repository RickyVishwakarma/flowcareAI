"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, isAuthed } from "@/lib/api";

export function VerifyBanner() {
  const pathname = usePathname();
  const router = useRouter();
  const [unverified, setUnverified] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!isAuthed()) {
      setUnverified(false);
      return;
    }
    api
      .me()
      .then((m) => setUnverified(!m.email_verified))
      .catch(() => setUnverified(false));
  }, [pathname]);

  if (!unverified) return null;

  async function resend() {
    setSending(true);
    setFlash(null);
    try {
      const r = await api.resendVerification();
      if (r.verification_link) {
        // Dev: no real inbox — surface the link so it's one click to verify.
        setDevLink(r.verification_link);
        setFlash("Dev mode: no real email is sent. Click “Verify now”.");
      } else {
        setFlash("Verification email sent — check your inbox.");
      }
    } catch (e) {
      setFlash((e as Error).message);
    } finally {
      setSending(false);
    }
  }

  function verifyNow() {
    if (!devLink) return;
    const search = new URL(devLink).search;
    router.push(`/verify-email${search}`);
  }

  return (
    <div className="border-b border-amber-200 bg-amber-50">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-3 gap-y-1 px-6 py-2 text-sm text-amber-800">
        <span>⚠ Your email isn't verified yet.</span>
        {devLink ? (
          <button onClick={verifyNow} className="rounded bg-amber-600 px-2 py-0.5 font-medium text-white hover:bg-amber-700">
            Verify now →
          </button>
        ) : (
          <button
            onClick={resend}
            disabled={sending}
            className="font-medium underline hover:text-amber-900 disabled:opacity-50"
          >
            {sending ? "Sending…" : "Resend verification"}
          </button>
        )}
        {flash && <span className="text-amber-700">{flash}</span>}
      </div>
    </div>
  );
}
