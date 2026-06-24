"use client";

import { useEffect, useState } from "react";
import { api, type Workflow } from "@/lib/api";
import { WorkflowCanvas } from "@/components/WorkflowCanvas";
import { WorkflowEditor } from "@/components/WorkflowEditor";

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [active, setActive] = useState<Workflow | null>(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listWorkflows()
      .then((w) => {
        setWorkflows(w);
        setActive(w[0] ?? null);
      })
      .catch((e) => setError((e as Error).message));
  }, []);

  function select(w: Workflow) {
    setActive(w);
    setEditing(false);
  }

  async function newWorkflow() {
    const name = window.prompt("Workflow name", "New workflow");
    if (!name) return;
    try {
      const created = await api.createWorkflow({
        name,
        trigger_event: "referral.received",
        status: "draft",
        nodes: [],
      });
      setWorkflows((ws) => [...ws, created]);
      setActive(created);
      setEditing(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function onSaved(saved: Workflow) {
    setWorkflows((ws) => ws.map((w) => (w.id === saved.id ? saved : w)));
    setActive(saved);
    setEditing(false);
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="eyebrow">Automation</span>
          <h1 className="mt-3 text-3xl font-extrabold">Workflow Builder</h1>
          <p className="mt-1 text-slate-500">Design the automations that run on every incoming referral.</p>
        </div>
        <button onClick={newWorkflow} className="btn-primary">+ New workflow</button>
      </div>
      {error && <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error} — sign in first.</p>}

      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <aside className="card p-4">
          <h3 className="text-xs font-semibold uppercase text-slate-400">Workflows</h3>
          <ul className="mt-2 space-y-1">
            {workflows.map((w) => (
              <li key={w.id}>
                <button
                  onClick={() => select(w)}
                  className={`w-full rounded-lg px-2.5 py-1.5 text-left text-sm transition ${
                    active?.id === w.id ? "bg-brand text-white" : "hover:bg-slate-100"
                  }`}
                >
                  {w.name}
                  <span className="ml-1 text-xs opacity-70">({w.status})</span>
                </button>
              </li>
            ))}
            {workflows.length === 0 && <li className="text-sm text-slate-400">No workflows yet.</li>}
          </ul>
        </aside>

        <section className="card min-w-0 p-4">
          {!active ? (
            <p className="text-sm text-slate-500">Select or create a workflow.</p>
          ) : editing ? (
            <WorkflowEditor
              key={active.id}
              workflow={active}
              onSaved={onSaved}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <>
              <div className="mb-3 flex items-baseline justify-between">
                <div>
                  <h2 className="font-semibold">{active.name}</h2>
                  <p className="text-xs text-slate-500">
                    Trigger: <code>{active.trigger_event}</code> · v{active.version} ·{" "}
                    <span className="rounded-full bg-teal-100 px-2 py-0.5 text-teal-700">{active.status}</span>
                  </p>
                </div>
                <button onClick={() => setEditing(true)} className="btn-ghost">
                  Edit
                </button>
              </div>
              <WorkflowCanvas nodes={active.nodes} />
            </>
          )}
        </section>
      </div>
    </div>
  );
}
