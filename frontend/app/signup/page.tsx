"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setTokens } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [org, setOrg] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await api.signup(org, email, password, fullName || undefined);
      setTokens(result.access_token, result.refresh_token);
      // In dev the backend returns the verification link so we can complete the
      // flow in-browser (simulating clicking the email). In prod it's null and a
      // real email is sent; we just land on the dashboard with the verify banner.
      if (result.verification_link) {
        const search = new URL(result.verification_link).search;
        router.push(`/verify-email${search}`);
      } else {
        router.push("/referrals");
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="text-2xl font-bold">Create your organization</h1>
      <p className="mt-1 text-sm text-slate-600">
        You'll be the admin. Add teammates later from the app.
      </p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <Field label="Organization name" value={org} onChange={setOrg} required />
        <Field label="Your name" value={fullName} onChange={setFullName} />
        <Field label="Email" value={email} onChange={setEmail} type="email" required />
        <Field label="Password (min 8 chars)" value={password} onChange={setPassword} type="password" required />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          disabled={loading}
          className="w-full rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
        >
          {loading ? "Creating…" : "Create organization"}
        </button>
      </form>
      <p className="mt-4 text-sm text-slate-600">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-brand hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}

function Field({
  label, value, onChange, type = "text", required,
}: {
  label: string; value: string; onChange: (v: string) => void; type?: string; required?: boolean;
}) {
  return (
    <div>
      <label className="block text-sm font-medium">{label}</label>
      <input
        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        type={type}
        required={required}
      />
    </div>
  );
}
