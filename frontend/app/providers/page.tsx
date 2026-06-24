"use client";

import { useEffect, useState } from "react";
import { api, type Provider } from "@/lib/api";

const SPECIALTIES = [
  "cardiology", "neurology", "orthopedics", "endocrinology",
  "pulmonology", "gastroenterology", "dermatology",
];

export default function ProvidersPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "", specialty: "cardiology", accepted_insurances: "", location: "",
    in_network: true, current_wait_days: 7,
  });

  async function load() {
    try {
      setProviders(await api.listProviders());
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.createProvider({
        name: form.name,
        specialty: form.specialty,
        accepted_insurances: form.accepted_insurances.split(",").map((s) => s.trim()).filter(Boolean),
        location: form.location || null,
        in_network: form.in_network,
        current_wait_days: Number(form.current_wait_days),
      });
      setShowForm(false);
      setForm({ ...form, name: "", accepted_insurances: "", location: "" });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Provider Directory</h1>
          <p className="text-sm text-slate-600">Used to match referrals and flag out-of-network leakage.</p>
        </div>
        <button onClick={() => setShowForm((v) => !v)} className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark">
          {showForm ? "Close" : "+ Add provider"}
        </button>
      </div>

      {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error} — sign in first.</p>}

      {showForm && (
        <form onSubmit={add} className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required />
          <label className="block text-sm">
            <span className="font-medium text-slate-600">Specialty</span>
            <select value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5">
              {SPECIALTIES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <Field label="Accepted insurances (comma-sep)" value={form.accepted_insurances} onChange={(v) => setForm({ ...form, accepted_insurances: v })} placeholder="Aetna, Cigna, United" />
          <Field label="Location" value={form.location} onChange={(v) => setForm({ ...form, location: v })} />
          <Field label="Wait (days)" value={String(form.current_wait_days)} onChange={(v) => setForm({ ...form, current_wait_days: Number(v) || 0 })} type="number" />
          <label className="flex items-center gap-2 self-end text-sm text-slate-600">
            <input type="checkbox" checked={form.in_network} onChange={(e) => setForm({ ...form, in_network: e.target.checked })} />
            In-network
          </label>
          <div className="sm:col-span-2 lg:col-span-3">
            <button className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark">Save provider</button>
          </div>
        </form>
      )}

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2">Provider</th>
              <th className="px-4 py-2">Specialty</th>
              <th className="px-4 py-2">Network</th>
              <th className="px-4 py-2">Accepted insurances</th>
              <th className="px-4 py-2">Wait</th>
            </tr>
          </thead>
          <tbody>
            {providers.map((p) => (
              <tr key={p.id} className="border-t border-slate-100">
                <td className="px-4 py-2">
                  <div className="font-medium">{p.name}</div>
                  {p.location && <div className="text-xs text-slate-400">{p.location}</div>}
                </td>
                <td className="px-4 py-2 capitalize">{p.specialty}</td>
                <td className="px-4 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${p.in_network ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                    {p.in_network ? "in-network" : "out-of-network"}
                  </span>
                </td>
                <td className="px-4 py-2 text-xs text-slate-500">{p.accepted_insurances.join(", ") || "—"}</td>
                <td className="px-4 py-2">{p.current_wait_days}d</td>
              </tr>
            ))}
            {providers.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">No providers yet — add one to enable matching.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, type = "text", required }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; type?: string; required?: boolean }) {
  return (
    <label className="block text-sm">
      <span className="font-medium text-slate-600">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} type={type} required={required} className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5" />
    </label>
  );
}
