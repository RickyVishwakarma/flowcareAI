"use client";

import { useEffect, useState } from "react";
import { api, type MatchResult, type Referral, type ReferralDetail } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  received: "bg-slate-100 text-slate-700",
  processing: "bg-blue-100 text-blue-700",
  validated: "bg-green-100 text-green-700",
  needs_review: "bg-amber-100 text-amber-700",
  scheduled: "bg-teal-100 text-teal-700",
  failed: "bg-red-100 text-red-700",
};

export default function ReferralsPage() {
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [selected, setSelected] = useState<ReferralDetail | null>(null);
  const [match, setMatch] = useState<MatchResult | null>(null);
  const [matching, setMatching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function refresh() {
    try {
      setReferrals(await api.listReferrals());
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadReferral(file);
      setTimeout(refresh, 800); // give the worker a moment
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function view(id: string) {
    setMatch(null);
    setSelected(await api.getReferral(id));
  }

  async function findProvider() {
    if (!selected) return;
    setMatching(true);
    setError(null);
    try {
      setMatch(await api.matchProvider(selected.id));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setMatching(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Referrals</h1>
        <label className="cursor-pointer rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark">
          {uploading ? "Uploading…" : "Upload referral"}
          <input type="file" className="hidden" onChange={onUpload} accept=".pdf,.png,.jpg,.jpeg,.txt" />
        </label>
      </div>

      {error && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error} — make sure you are signed in.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500">
              <tr>
                <th className="px-4 py-2">Code</th>
                <th className="px-4 py-2">Patient</th>
                <th className="px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {referrals.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => view(r.id)}
                  className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                >
                  <td className="px-4 py-2 font-mono text-xs">{r.reference_code}</td>
                  <td className="px-4 py-2">{r.patient_name ?? "—"}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_COLORS[r.status] ?? "bg-slate-100"}`}>
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
              {referrals.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-slate-400">
                    No referrals yet — upload one to see the pipeline run.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {selected && (
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="font-semibold">{selected.reference_code}</h2>
            {selected.extracted_data ? (
              <dl className="mt-3 space-y-1 text-sm">
                <Row label="Patient" value={selected.extracted_data.patient_name} />
                <Row label="DOB" value={selected.extracted_data.dob} />
                <Row label="Insurance" value={selected.extracted_data.insurance_provider} />
                <Row label="Member ID" value={selected.extracted_data.insurance_member_id} />
                <Row label="Diagnosis" value={selected.extracted_data.diagnosis} />
                <Row label="Reason" value={selected.extracted_data.referral_reason} />
                <Row
                  label="Confidence"
                  value={
                    selected.extracted_data.overall_confidence != null
                      ? `${Math.round(selected.extracted_data.overall_confidence * 100)}% (${selected.extracted_data.extractor})`
                      : null
                  }
                />
                <Row label="Validation" value={selected.extracted_data.validation_status} />
                {selected.extracted_data.validation_report?.warnings?.length > 0 && (
                  <div className="pt-2 text-amber-700">
                    {selected.extracted_data.validation_report.warnings.map((w) => (
                      <p key={w}>⚠ {w}</p>
                    ))}
                  </div>
                )}
              </dl>
            ) : (
              <p className="mt-3 text-sm text-slate-500">Still processing…</p>
            )}

            {/* Provider matching */}
            <div className="mt-4 border-t border-slate-100 pt-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-700">Provider match</span>
                <button
                  onClick={findProvider}
                  disabled={matching}
                  className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium hover:border-brand disabled:opacity-50"
                >
                  {matching ? "Matching…" : "Find provider"}
                </button>
              </div>
              {match && (
                <div className="mt-2 space-y-2 text-sm">
                  {match.leakage_risk && (
                    <p className="rounded-md bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700">
                      ⚠ Leakage risk — no in-network provider serves this patient
                      {match.specialty ? ` (${match.specialty}` : ""}
                      {match.insurance ? ` · ${match.insurance})` : match.specialty ? ")" : ""}
                    </p>
                  )}
                  {match.chosen ? (
                    <div className="rounded-md bg-slate-50 p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{match.chosen.name}</span>
                        <span className={`rounded-full px-2 py-0.5 text-xs ${match.chosen.in_network ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                          {match.chosen.in_network ? "in-network" : "out-of-network"}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {match.chosen.specialty} · {match.chosen.wait_days}d wait · score {match.chosen.score}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">{match.chosen.reasons.join(" · ")}</p>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400">No matching provider found for this referral.</p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium">{value ?? "—"}</dd>
    </div>
  );
}
