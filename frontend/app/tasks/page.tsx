"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type TaskItem } from "@/lib/api";

const FILTERS = [
  { key: "", label: "All" },
  { key: "open", label: "Open" },
  { key: "in_progress", label: "In progress" },
  { key: "done", label: "Done" },
] as const;

const PRIORITY_STYLE: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  normal: "bg-slate-100 text-slate-600",
  low: "bg-slate-100 text-slate-400",
};
const STATUS_STYLE: Record<string, string> = {
  open: "bg-amber-100 text-amber-700",
  in_progress: "bg-blue-100 text-blue-700",
  done: "bg-green-100 text-green-700",
  cancelled: "bg-slate-100 text-slate-500",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [filter, setFilter] = useState<string>("");
  const [mine, setMine] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setTasks(await api.listTasks({ status: filter || undefined, mine }));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [filter, mine]);

  useEffect(() => {
    load();
  }, [load]);

  async function act(id: string, fn: () => Promise<unknown>) {
    setBusy(id);
    try {
      await fn();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Task Inbox</h1>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />
          Assigned to me
        </label>
      </div>

      <div className="flex gap-1">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`rounded-md px-3 py-1 text-sm ${filter === f.key ? "bg-brand text-white" : "bg-white text-slate-600 hover:bg-slate-100"}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error} — sign in first.</p>}

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2">Task</th>
              <th className="px-4 py-2">Priority</th>
              <th className="px-4 py-2">Referral</th>
              <th className="px-4 py-2">Assignee</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id} className="border-t border-slate-100">
                <td className="px-4 py-3">
                  <div className="font-medium">{t.title}</div>
                  {t.description && <div className="text-xs text-slate-400">{t.description}</div>}
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${PRIORITY_STYLE[t.priority] ?? ""}`}>{t.priority}</span>
                </td>
                <td className="px-4 py-3">
                  {t.referral_id ? (
                    <Link href={`/referrals`} className="font-mono text-xs text-brand hover:underline">
                      {t.referral_reference ?? t.referral_id.slice(0, 8)}
                    </Link>
                  ) : (
                    <span className="text-slate-300">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-slate-500">{t.assignee_email ?? "Unassigned"}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_STYLE[t.status] ?? ""}`}>
                    {t.status.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    {!t.assigned_to && t.status !== "done" && (
                      <button
                        disabled={busy === t.id}
                        onClick={() => act(t.id, () => api.claimTask(t.id))}
                        className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:border-brand disabled:opacity-50"
                      >
                        Claim
                      </button>
                    )}
                    {t.status !== "done" && t.status !== "cancelled" && (
                      <button
                        disabled={busy === t.id}
                        onClick={() => act(t.id, () => api.updateTask(t.id, { status: "done" }))}
                        className="rounded bg-brand px-2 py-0.5 text-xs font-medium text-white hover:bg-brand-dark disabled:opacity-50"
                      >
                        Done
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {tasks.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-slate-400">
                  No tasks here. Workflows that hit a “create task” action will show up automatically.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
