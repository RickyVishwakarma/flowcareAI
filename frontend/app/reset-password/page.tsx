"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api } from "@/lib/api";

function ResetInner() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) {
      setError("Missing reset token.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api.resetPassword(token, password);
      setDone(true);
      setTimeout(() => router.push("/login"), 1500);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="mx-auto max-w-sm rounded-lg border border-green-200 bg-green-50 p-6 text-center">
        <p className="text-lg font-semibold text-green-700">✓ Password reset</p>
        <p className="mt-1 text-sm text-green-700">Redirecting you to sign in…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto mt-10 max-w-sm card p-8">
      <h1 className="text-2xl font-bold">Choose a new password</h1>
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div>
          <label className="block text-sm font-medium">New password (min 8 chars)</label>
          <input
            className="mt-1 w-full rounded-md border border-white/15 px-3 py-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            minLength={8}
            required
          />
        </div>
        {!token && <p className="text-sm text-amber-600">No reset token in the URL — use the link from your email.</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          disabled={loading || !token}
          className="w-full rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
        >
          {loading ? "Resetting…" : "Reset password"}
        </button>
      </form>
      <Link href="/login" className="mt-4 inline-block text-sm text-brand hover:underline">
        Back to sign in
      </Link>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<p className="text-center text-slate-400">Loading…</p>}>
      <ResetInner />
    </Suspense>
  );
}
