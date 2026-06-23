"use client";

import { useEffect, useState } from "react";
import { api, type DashboardStats } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  received: "#94a3b8",
  processing: "#60a5fa",
  extracted: "#818cf8",
  validated: "#34d399",
  needs_review: "#fbbf24",
  insurance_verified: "#2dd4bf",
  scheduled: "#14b8a6",
  completed: "#10b981",
  failed: "#f87171",
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.dashboard().then(setStats).catch((e) => setError((e as Error).message));
  }, []);

  if (error) {
    return <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error} — sign in first.</p>;
  }
  if (!stats) return <p className="text-slate-500">Loading dashboard…</p>;

  const pct = (n: number) => `${Math.round(n * 100)}%`;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Operations Dashboard</h1>

      {/* KPI cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <Kpi label="Total referrals" value={stats.referrals_total} />
        <Kpi label="Review queue" value={stats.review_queue_size} accent={stats.review_queue_size > 0 ? "amber" : undefined} />
        <Kpi label="Workflow success" value={pct(stats.workflow_success_rate)} sub={`${stats.workflow_total} runs`} />
        <Kpi label="Insurance active" value={pct(stats.insurance_active_rate)} sub={`${stats.insurance_active}/${stats.insurance_total}`} />
        <Kpi label="Appointments" value={stats.appointments_total} />
        <Kpi
          label="Leakage flagged"
          value={stats.leakage_flagged}
          sub={`${stats.providers_total} providers`}
          accent={stats.leakage_flagged > 0 ? "amber" : undefined}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Referrals over time */}
        <Card title="Referrals — last 14 days">
          <TimeBars data={stats.referrals_timeseries} />
        </Card>

        {/* Status breakdown */}
        <Card title="Referrals by status">
          <BreakdownBars data={stats.referrals_by_status} colors={STATUS_COLOR} total={stats.referrals_total} />
        </Card>

        {/* Validation */}
        <Card title="Validation outcomes">
          <BreakdownBars
            data={stats.validation_breakdown}
            colors={{ passed: "#34d399", passed_with_warnings: "#fbbf24", failed: "#f87171" }}
            total={Object.values(stats.validation_breakdown).reduce((a, b) => a + b, 0)}
          />
        </Card>

        {/* Source + extractor */}
        <Card title="Intake sources & extractor">
          <div className="grid grid-cols-2 gap-4">
            <BreakdownBars data={stats.referrals_by_source} colors={{}} total={stats.referrals_total} />
            <BreakdownBars data={stats.extractor_breakdown} colors={{ claude: "#a78bfa", template: "#94a3b8", human_review: "#34d399" }} total={Object.values(stats.extractor_breakdown).reduce((a, b) => a + b, 0)} />
          </div>
        </Card>
      </div>
    </div>
  );
}

function Kpi({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: "amber" }) {
  return (
    <div className={`rounded-lg border bg-white p-4 ${accent === "amber" ? "border-amber-300" : "border-slate-200"}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent === "amber" ? "text-amber-600" : "text-slate-900"}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="mb-4 text-sm font-semibold text-slate-700">{title}</h2>
      {children}
    </div>
  );
}

function TimeBars({ data }: { data: { date: string; count: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  const W = 100 / data.length;
  return (
    <svg viewBox="0 0 100 40" className="w-full" preserveAspectRatio="none" style={{ height: 140 }}>
      {data.map((d, i) => {
        const h = (d.count / max) * 34;
        return (
          <g key={d.date}>
            <rect x={i * W + 1} y={36 - h} width={W - 2} height={h} fill="#0d9488" rx={0.6} />
            {d.count > 0 && (
              <text x={i * W + W / 2} y={34 - h} fontSize={2.6} textAnchor="middle" fill="#475569">
                {d.count}
              </text>
            )}
            <text x={i * W + W / 2} y={39.5} fontSize={2.2} textAnchor="middle" fill="#94a3b8">
              {d.date.slice(5)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function BreakdownBars({ data, colors, total }: { data: Record<string, number>; colors: Record<string, string>; total: number }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) return <p className="text-sm text-slate-400">No data yet.</p>;
  const palette = ["#0d9488", "#60a5fa", "#a78bfa", "#fbbf24", "#f87171", "#34d399"];
  return (
    <div className="space-y-2">
      {entries.map(([label, count], i) => {
        const w = total ? (count / total) * 100 : 0;
        return (
          <div key={label}>
            <div className="flex justify-between text-xs text-slate-600">
              <span className="capitalize">{label.replace(/_/g, " ")}</span>
              <span className="font-medium">{count}</span>
            </div>
            <div className="mt-0.5 h-2 w-full rounded-full bg-slate-100">
              <div
                className="h-2 rounded-full"
                style={{ width: `${w}%`, background: colors[label] ?? palette[i % palette.length] }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
