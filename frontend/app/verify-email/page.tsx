"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";

function VerifyInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"verifying" | "ok" | "error">("verifying");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("Missing verification token.");
      return;
    }
    api
      .verifyEmail(token)
      .then((r) => {
        setState("ok");
        setMessage(r.detail);
      })
      .catch((e) => {
        setState("error");
        setMessage((e as Error).message);
      });
  }, [token]);

  return (
    <div className="mx-auto max-w-md text-center">
      {state === "verifying" && <p className="text-slate-300">Verifying your email…</p>}
      {state === "ok" && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-6">
          <p className="text-lg font-semibold text-green-700">✓ Email verified</p>
          <p className="mt-1 text-sm text-green-700">{message}</p>
          <Link href="/referrals" className="mt-4 inline-block rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark">
            Go to dashboard
          </Link>
        </div>
      )}
      {state === "error" && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <p className="text-lg font-semibold text-red-700">Verification failed</p>
          <p className="mt-1 text-sm text-red-700">{message}</p>
          <Link href="/login" className="mt-4 inline-block text-sm font-medium text-brand hover:underline">
            Back to sign in
          </Link>
        </div>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<p className="text-center text-slate-400">Loading…</p>}>
      <VerifyInner />
    </Suspense>
  );
}
