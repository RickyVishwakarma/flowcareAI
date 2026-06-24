"use client";

import { useEffect, useState } from "react";
import {
  api,
  REVIEW_FIELDS,
  type ReviewDetail,
  type ReviewQueueItem,
} from "@/lib/api";

const LABELS: Record<string, string> = {
  patient_name: "Patient name",
  dob: "Date of birth",
  insurance_provider: "Insurance provider",
  insurance_member_id: "Member ID",
  referring_doctor: "Referring doctor",
  diagnosis: "Diagnosis",
  referral_reason: "Referral reason",
};

export default function ReviewPage() {
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);
  const [detail, setDetail] = useState<ReviewDetail | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [rerun, setRerun] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function refreshQueue() {
    try {
      setQueue(await api.reviewQueue());
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    refreshQueue();
  }, []);

  async function open(id: string) {
    setFlash(null);
    const d = await api.getReview(id);
    setDetail(d);
    setForm(
      Object.fromEntries(REVIEW_FIELDS.map((f) => [f, d.fields[f] ?? ""])),
    );
  }

  async function save() {
    if (!detail) return;
    setSaving(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { rerun_workflow: rerun };
      for (const f of REVIEW_FIELDS) body[f] = form[f] || null;
      const result = await api.submitReview(detail.id, body);
      setFlash(
        `Saved — status: ${result.status} (${result.validation_status}); ` +
          `${result.workflow_executions.length} workflow run(s).`,
      );
      setDetail(null);
      await refreshQueue();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const errors = detail?.validation_report?.errors ?? [];
  const warnings = detail?.validation_report?.warnings ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Review Queue</h1>
        <p className="text-sm text-slate-600">
          Referrals that failed automatic validation. Correct the fields and re-run.
        </p>
      </div>

      {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {flash && <p className="rounded-md bg-green-50 p-3 text-sm text-green-700">{flash}</p>}

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-xs font-semibold uppercase text-slate-500">
            Awaiting review ({queue.length})
          </div>
          <ul>
            {queue.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => open(item.id)}
                  className={`w-full border-t border-slate-100 px-4 py-3 text-left hover:bg-slate-50 ${
                    detail?.id === item.id ? "bg-amber-50" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{item.patient_name ?? "Unknown patient"}</span>
                    <span className="font-mono text-xs text-slate-400">{item.reference_code}</span>
                  </div>
                  <div className="mt-1 flex gap-2 text-xs">
                    <span className="rounded bg-red-100 px-1.5 py-0.5 text-red-700">
                      {item.error_count} error{item.error_count === 1 ? "" : "s"}
                    </span>
                    {item.warning_count > 0 && (
                      <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-700">
                        {item.warning_count} warning{item.warning_count === 1 ? "" : "s"}
                      </span>
                    )}
                  </div>
                </button>
              </li>
            ))}
            {queue.length === 0 && (
              <li className="px-4 py-8 text-center text-sm text-slate-400">
                Nothing to review — the queue is clear. 🎉
              </li>
            )}
          </ul>
        </div>

        {detail ? (
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="mb-4 flex items-baseline justify-between">
              <h2 className="font-semibold">{detail.reference_code}</h2>
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                {detail.status}
              </span>
            </div>

            {(errors.length > 0 || warnings.length > 0) && (
              <div className="mb-4 space-y-1 rounded-md bg-amber-50 p-3 text-sm">
                {errors.map((e) => (
                  <p key={e} className="text-red-700">✕ {e}</p>
                ))}
                {warnings.map((w) => (
                  <p key={w} className="text-amber-700">⚠ {w}</p>
                ))}
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              {REVIEW_FIELDS.map((f) => {
                const conf = detail.field_confidence[f];
                const low = conf != null && conf < 0.5;
                return (
                  <div key={f}>
                    <label className="flex items-center justify-between text-sm font-medium">
                      {LABELS[f]}
                      {conf != null && (
                        <span className={`text-xs ${low ? "text-red-500" : "text-slate-400"}`}>
                          {Math.round(conf * 100)}%
                        </span>
                      )}
                    </label>
                    <input
                      className={`mt-1 w-full rounded-md border px-3 py-2 ${
                        low ? "border-red-300 bg-red-50" : "border-slate-300"
                      }`}
                      value={form[f] ?? ""}
                      onChange={(e) => setForm({ ...form, [f]: e.target.value })}
                    />
                  </div>
                );
              })}
            </div>

            <details className="mt-4">
              <summary className="cursor-pointer text-sm text-slate-500">View OCR text</summary>
              <pre className="mt-2 max-h-48 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-600">
                {detail.ocr_text ?? "(no text)"}
              </pre>
            </details>

            <div className="mt-5 flex items-center gap-4">
              <button
                onClick={save}
                disabled={saving}
                className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save & re-validate"}
              </button>
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={rerun}
                  onChange={(e) => setRerun(e.target.checked)}
                />
                Re-run workflow if validation passes
              </label>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white p-12 text-sm text-slate-400">
            Select a referral from the queue to review.
          </div>
        )}
      </div>
    </div>
  );
}
