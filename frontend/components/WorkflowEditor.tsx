"use client";

import { useMemo, useRef, useState } from "react";
import { api, type Workflow, type WorkflowNode } from "@/lib/api";
import { layeredLayout } from "@/lib/layout";

// ── Node catalog ─────────────────────────────────────────────────────
const TRIGGERS = ["referral.received", "patient.created", "insurance.verified", "appointment.scheduled"];
const CONDITIONS = ["if", "switch"];
const ACTIONS = [
  "verify_insurance", "schedule_appointment", "send_email", "send_sms",
  "create_task", "update_status", "call_api", "send_webhook",
];

const KIND_STYLE: Record<string, string> = {
  trigger: "border-violet-400 bg-violet-50",
  condition: "border-amber-400 bg-amber-50",
  action: "border-sky-400 bg-sky-50",
};
const NODE_W = 184;
const HEAD_H = 46;
const ROW_H = 22;

interface ENode {
  node_key: string;
  kind: string;
  type: string;
  config: Record<string, any>;
  next: Record<string, string>;
  position: { x: number; y: number };
}

function kindOf(type: string): string {
  if (TRIGGERS.includes(type)) return "trigger";
  if (CONDITIONS.includes(type)) return "condition";
  return "action";
}

function outcomesOf(n: ENode): string[] {
  if (n.kind === "condition" && n.type === "if") return ["true", "false"];
  if (n.kind === "condition" && n.type === "switch") {
    const cases = (n.config.cases as { label: string }[] | undefined) ?? [];
    return [...cases.map((c) => c.label || "case"), "default"];
  }
  return ["default"];
}

function nodeHeight(n: ENode): number {
  return HEAD_H + outcomesOf(n).length * ROW_H;
}

function hasSavedPositions(nodes: WorkflowNode[]): boolean {
  return nodes.length > 0 && nodes.every((n) => typeof (n as any).position?.x === "number");
}

function clone(nodes: WorkflowNode[]): ENode[] {
  return nodes.map((n) => ({
    node_key: n.node_key,
    kind: n.kind,
    type: n.type,
    config: { ...(n.config as Record<string, any>) },
    next: { ...(n.next as Record<string, string>) },
    position:
      (n as any).position && typeof (n as any).position.x === "number"
        ? { ...(n as any).position }
        : { x: 0, y: 0 },
  }));
}

// Layered layout: columns by flow depth (BFS from the trigger), aligned rows.
const COL_W = 250;
const ROW_GAP = 140;
const PAD = 32;

function autoLayout(nodes: ENode[]): ENode[] {
  if (nodes.length === 0) return nodes;
  const positions = layeredLayout(nodes, { colWidth: COL_W, rowGap: ROW_GAP, pad: PAD });
  return nodes.map((n) => ({ ...n, position: positions.get(n.node_key) ?? n.position }));
}

export function WorkflowEditor({
  workflow,
  onSaved,
  onCancel,
}: {
  workflow: Workflow;
  onSaved: (w: Workflow) => void;
  onCancel: () => void;
}) {
  const [nodes, setNodes] = useState<ENode[]>(() => {
    const cloned = clone(workflow.nodes);
    // Respect hand-placed layouts; otherwise lay the graph out cleanly.
    return hasSavedPositions(workflow.nodes) ? cloned : autoLayout(cloned);
  });
  const [name, setName] = useState(workflow.name);
  const [triggerEvent, setTriggerEvent] = useState(workflow.trigger_event);
  const [active, setActive] = useState(workflow.status === "active");
  const [selected, setSelected] = useState<string | null>(null);
  const [linking, setLinking] = useState<{ from: string; outcome: string } | null>(null);
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [showPalette, setShowPalette] = useState(true);
  const [showInspector, setShowInspector] = useState(true);

  const contentRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;
  const dragRef = useRef<{ key: string; ox: number; oy: number; sx: number; sy: number } | null>(null);
  const keySeq = useRef(1);

  const byKey = useMemo(() => new Map(nodes.map((n) => [n.node_key, n])), [nodes]);

  // Convert client (screen) coords to unscaled canvas coords — divide by zoom
  // since the content is visually scaled via a CSS transform.
  function toCanvas(clientX: number, clientY: number) {
    const r = contentRef.current!.getBoundingClientRect();
    return { x: (clientX - r.left) / zoom, y: (clientY - r.top) / zoom };
  }

  function zoomTo(z: number) {
    setZoom(Math.min(2, Math.max(0.25, Math.round(z * 100) / 100)));
  }

  function fitToView() {
    const wrap = scrollRef.current;
    if (!wrap || nodes.length === 0) {
      setZoom(1);
      return;
    }
    const maxX = Math.max(...nodes.map((n) => n.position.x + NODE_W)) + PAD;
    const maxY = Math.max(...nodes.map((n) => n.position.y + nodeHeight(n))) + PAD;
    zoomTo(Math.min(wrap.clientWidth / maxX, wrap.clientHeight / maxY, 1.5));
    wrap.scrollTo({ left: 0, top: 0 });
  }

  function update(key: string, patch: Partial<ENode>) {
    setNodes((ns) => ns.map((n) => (n.node_key === key ? { ...n, ...patch } : n)));
  }

  // ── Palette drag-and-drop ──
  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    const type = e.dataTransfer.getData("text/plain");
    if (!type) return;
    const { x, y } = toCanvas(e.clientX, e.clientY);
    const kind = kindOf(type);
    let key = `${type.replace(/[^a-z0-9]+/gi, "_")}_${keySeq.current++}`;
    while (byKey.has(key)) key = `${type.replace(/[^a-z0-9]+/gi, "_")}_${keySeq.current++}`;
    const node: ENode = {
      node_key: key,
      kind,
      type,
      config: type === "switch" ? { cases: [{ label: "case1", field: "", op: "eq", value: "" }] } : {},
      next: {},
      position: { x: Math.max(0, x - NODE_W / 2), y: Math.max(0, y - HEAD_H / 2) },
    };
    setNodes((ns) => [...ns, node]);
    setSelected(key);
  }

  // ── Node move ──
  function onNodePointerDown(e: React.PointerEvent, key: string) {
    if ((e.target as HTMLElement).dataset.handle) return; // handle starts a link, not a move
    e.stopPropagation();
    setSelected(key);
    const n = byKey.get(key)!;
    const c = toCanvas(e.clientX, e.clientY);
    dragRef.current = { key, ox: n.position.x, oy: n.position.y, sx: c.x, sy: c.y };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onNodePointerMove(e: React.PointerEvent) {
    const d = dragRef.current;
    if (!d) return;
    const c = toCanvas(e.clientX, e.clientY);
    update(d.key, { position: { x: Math.max(0, d.ox + c.x - d.sx), y: Math.max(0, d.oy + c.y - d.sy) } });
  }
  function onNodePointerUp(e: React.PointerEvent) {
    if (dragRef.current) {
      (e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId);
      dragRef.current = null;
    }
  }

  // ── Edge linking ──
  function startLink(e: React.PointerEvent, from: string, outcome: string) {
    e.stopPropagation();
    setLinking({ from, outcome });
    const move = (ev: PointerEvent) => setCursor(toCanvas(ev.clientX, ev.clientY));
    const up = (ev: PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      const pt = toCanvas(ev.clientX, ev.clientY);
      const target = nodesRef.current.find(
        (n) =>
          n.node_key !== from &&
          pt.x >= n.position.x && pt.x <= n.position.x + NODE_W &&
          pt.y >= n.position.y && pt.y <= n.position.y + nodeHeight(n),
      );
      if (target) {
        setNodes((ns) =>
          ns.map((n) => (n.node_key === from ? { ...n, next: { ...n.next, [outcome]: target.node_key } } : n)),
        );
      }
      setLinking(null);
      setCursor(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function removeEdge(from: string, outcome: string) {
    setNodes((ns) =>
      ns.map((n) => {
        if (n.node_key !== from) return n;
        const next = { ...n.next };
        delete next[outcome];
        return { ...n, next };
      }),
    );
  }

  function deleteNode(key: string) {
    setNodes((ns) =>
      ns
        .filter((n) => n.node_key !== key)
        .map((n) => ({
          ...n,
          next: Object.fromEntries(Object.entries(n.next).filter(([, t]) => t !== key)),
        })),
    );
    setSelected(null);
  }

  // ── Handle geometry ──
  function outPos(n: ENode, outcome: string) {
    const idx = outcomesOf(n).indexOf(outcome);
    return { x: n.position.x + NODE_W, y: n.position.y + HEAD_H + idx * ROW_H + ROW_H / 2 };
  }
  function inPos(n: ENode) {
    return { x: n.position.x, y: n.position.y + HEAD_H / 2 };
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name,
        description: workflow.description,
        trigger_event: triggerEvent,
        status: active ? "active" : "draft",
        nodes: nodes.map((n) => ({
          node_key: n.node_key,
          kind: n.kind,
          type: n.type,
          config: n.config,
          next: n.next,
          position: n.position,
        })),
      };
      const saved = await api.saveWorkflow(workflow.id, payload);
      onSaved(saved);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const selectedNode = selected ? byKey.get(selected) ?? null : null;
  const CANVAS_W = 2600;
  const CANVAS_H = 1600;

  return (
    <div className="fixed inset-x-0 bottom-0 top-14 z-20 flex flex-col gap-3 bg-slate-100 p-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-3">
        <span className="text-sm font-semibold text-slate-700">Editing:</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium"
        />
        <label className="text-xs text-slate-500">Trigger</label>
        <select
          value={triggerEvent}
          onChange={(e) => setTriggerEvent(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        >
          {TRIGGERS.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-sm text-slate-600">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          Active
        </label>
        {/* Zoom + panel toggles */}
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={() => setShowPalette((v) => !v)}
            className={`rounded-md border px-2 py-1 text-xs ${showPalette ? "border-brand bg-brand/10 text-brand-dark" : "border-slate-300 text-slate-500"}`}
          >
            Palette
          </button>
          <div className="flex items-center rounded-md border border-slate-300">
            <button onClick={() => zoomTo(zoom - 0.1)} className="px-2 py-1 hover:bg-slate-100" title="Zoom out">−</button>
            <span className="w-12 text-center text-xs tabular-nums text-slate-600">{Math.round(zoom * 100)}%</span>
            <button onClick={() => zoomTo(zoom + 0.1)} className="px-2 py-1 hover:bg-slate-100" title="Zoom in">+</button>
          </div>
          <button onClick={fitToView} className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-brand" title="Fit graph to view">
            Fit
          </button>
          <button
            onClick={() => setShowInspector((v) => !v)}
            className={`rounded-md border px-2 py-1 text-xs ${showInspector ? "border-brand bg-brand/10 text-brand-dark" : "border-slate-300 text-slate-500"}`}
          >
            Inspector
          </button>
        </div>

        <div className="ml-auto flex gap-2">
          <button
            onClick={() => setNodes((ns) => autoLayout(ns))}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:border-brand"
            title="Lay the graph out in clean columns"
          >
            Auto-arrange
          </button>
          <button onClick={onCancel} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:border-slate-400">
            Cancel
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="rounded-md bg-brand px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save graph"}
          </button>
        </div>
      </div>
      {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</p>}

      <div className="flex min-h-0 flex-1 gap-3">
        {/* Palette */}
        {showPalette && (
          <aside className="w-44 shrink-0 overflow-auto rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs font-semibold uppercase text-slate-400">Drag onto canvas</p>
            <PaletteGroup title="Triggers" items={TRIGGERS} color="bg-violet-100 text-violet-700" />
            <PaletteGroup title="Conditions" items={CONDITIONS} color="bg-amber-100 text-amber-700" />
            <PaletteGroup title="Actions" items={ACTIONS} color="bg-sky-100 text-sky-700" />
          </aside>
        )}

        {/* Canvas */}
        <div ref={scrollRef} className="h-full min-w-0 flex-1 overflow-auto rounded-lg border border-slate-200 bg-slate-50">
          {/* Sizer reserves the scaled dimensions so scrollbars track the zoom. */}
          <div style={{ width: CANVAS_W * zoom, height: CANVAS_H * zoom }}>
            <div
              ref={contentRef}
              className="relative origin-top-left"
              style={{ width: CANVAS_W, height: CANVAS_H, transform: `scale(${zoom})`, backgroundImage: "radial-gradient(#cbd5e1 1px, transparent 1px)", backgroundSize: "20px 20px" }}
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
              onPointerDown={() => setSelected(null)}
            >
            <svg className="pointer-events-none absolute inset-0" width={CANVAS_W} height={CANVAS_H}>
              {nodes.flatMap((n) =>
                Object.entries(n.next).map(([outcome, target]) => {
                  const to = byKey.get(target);
                  if (!to) return null;
                  const a = outPos(n, outcome);
                  const b = inPos(to);
                  const mx = (a.x + b.x) / 2;
                  return (
                    <path
                      key={`${n.node_key}-${outcome}`}
                      d={`M ${a.x} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`}
                      fill="none"
                      stroke="#94a3b8"
                      strokeWidth={1.5}
                    />
                  );
                }),
              )}
              {linking && cursor && (() => {
                const n = byKey.get(linking.from);
                if (!n) return null;
                const a = outPos(n, linking.outcome);
                return <path d={`M ${a.x} ${a.y} L ${cursor.x} ${cursor.y}`} stroke="#0d9488" strokeWidth={2} strokeDasharray="4 3" fill="none" />;
              })()}
            </svg>

            {nodes.map((n) => (
              <div
                key={n.node_key}
                onPointerDown={(e) => onNodePointerDown(e, n.node_key)}
                onPointerMove={onNodePointerMove}
                onPointerUp={onNodePointerUp}
                className={`absolute cursor-move select-none rounded-md border shadow-sm ${KIND_STYLE[n.kind]} ${selected === n.node_key ? "ring-2 ring-brand" : ""}`}
                style={{ left: n.position.x, top: n.position.y, width: NODE_W }}
              >
                {/* input handle */}
                <span className="absolute -left-1.5 top-5 h-3 w-3 rounded-full border-2 border-slate-400 bg-white" />
                <div className="px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-slate-400">{n.kind}</p>
                  <p className="truncate text-sm font-medium">{n.type}</p>
                </div>
                {/* output handles */}
                {outcomesOf(n).map((o, i) => (
                  <div key={o} className="flex items-center justify-end gap-1 pr-3" style={{ height: ROW_H }}>
                    <span className="text-[10px] text-slate-500">{o}</span>
                    <span
                      data-handle="1"
                      onPointerDown={(e) => startLink(e, n.node_key, o)}
                      title={`Drag to connect (${o})`}
                      className="absolute h-3 w-3 cursor-crosshair rounded-full border-2 border-brand bg-white hover:bg-brand"
                      style={{ right: -6, top: HEAD_H + i * ROW_H + ROW_H / 2 - 6 }}
                    />
                  </div>
                ))}
              </div>
            ))}

            {nodes.length === 0 && (
              <p className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-sm text-slate-400">
                Drag a node from the palette to begin.
              </p>
            )}
            </div>
          </div>
        </div>

        {/* Inspector */}
        {showInspector && (
          <aside className="w-72 shrink-0 overflow-auto rounded-lg border border-slate-200 bg-white p-3">
            {selectedNode ? (
              <Inspector
                node={selectedNode}
                onChange={(patch) => update(selectedNode.node_key, patch)}
                onDelete={() => deleteNode(selectedNode.node_key)}
                onRemoveEdge={(o) => removeEdge(selectedNode.node_key, o)}
              />
            ) : (
              <p className="text-sm text-slate-400">Select a node to edit its config, or drag a new one from the palette.</p>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}

function PaletteGroup({ title, items, color }: { title: string; items: string[]; color: string }) {
  return (
    <div className="mt-3">
      <p className="text-[11px] font-medium text-slate-500">{title}</p>
      <div className="mt-1 flex flex-col gap-1">
        {items.map((i) => (
          <span
            key={i}
            draggable
            onDragStart={(e) => e.dataTransfer.setData("text/plain", i)}
            className={`cursor-grab rounded px-1.5 py-1 text-[11px] ${color}`}
          >
            {i}
          </span>
        ))}
      </div>
    </div>
  );
}

// Friendly config fields per node type, with a JSON fallback.
const OPS = ["exists", "not_exists", "eq", "ne", "gt", "lt", "gte", "lte", "contains", "is_true", "is_false"];

function Inspector({
  node,
  onChange,
  onDelete,
  onRemoveEdge,
}: {
  node: ENode;
  onChange: (patch: Partial<ENode>) => void;
  onDelete: () => void;
  onRemoveEdge: (outcome: string) => void;
}) {
  const cfg = node.config;
  const set = (k: string, v: unknown) => onChange({ config: { ...cfg, [k]: v } });

  return (
    <div className="space-y-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-semibold">{node.type}</span>
        <button onClick={onDelete} className="text-xs text-red-600 hover:underline">
          Delete
        </button>
      </div>
      <p className="font-mono text-[11px] text-slate-400">{node.node_key}</p>

      {node.type === "if" && (
        <>
          <Field label="Field" value={cfg.field ?? ""} onChange={(v) => set("field", v)} placeholder="extracted.insurance_member_id" />
          <Select label="Operator" value={cfg.op ?? "exists"} options={OPS} onChange={(v) => set("op", v)} />
          {!["exists", "not_exists", "is_true", "is_false"].includes(cfg.op) && (
            <Field label="Value" value={cfg.value ?? ""} onChange={(v) => set("value", v)} />
          )}
        </>
      )}
      {node.type === "send_email" && (
        <>
          <Field label="To" value={cfg.to ?? ""} onChange={(v) => set("to", v)} placeholder="{{extracted.patient_email}}" />
          <Field label="Subject" value={cfg.subject ?? ""} onChange={(v) => set("subject", v)} />
          <Field label="Body" value={cfg.body ?? ""} onChange={(v) => set("body", v)} textarea />
        </>
      )}
      {node.type === "send_sms" && (
        <>
          <Field label="To" value={cfg.to ?? ""} onChange={(v) => set("to", v)} placeholder="+14155552671" />
          <Field label="Body" value={cfg.body ?? ""} onChange={(v) => set("body", v)} textarea />
        </>
      )}
      {node.type === "create_task" && (
        <>
          <Field label="Title" value={cfg.title ?? ""} onChange={(v) => set("title", v)} />
          <Select label="Priority" value={cfg.priority ?? "normal"} options={["low", "normal", "high"]} onChange={(v) => set("priority", v)} />
        </>
      )}
      {node.type === "update_status" && (
        <Field label="Status" value={cfg.status ?? ""} onChange={(v) => set("status", v)} placeholder="insurance_verified" />
      )}
      {(node.type === "call_api" || node.type === "send_webhook") && (
        <>
          <Field label="URL" value={cfg.url ?? ""} onChange={(v) => set("url", v)} />
          <Field label="Method" value={cfg.method ?? "POST"} onChange={(v) => set("method", v)} />
        </>
      )}
      {node.type === "switch" && (
        <JsonField label="Cases (JSON)" value={cfg.cases ?? []} onChange={(v) => set("cases", v)} />
      )}

      {Object.keys(node.next).length > 0 && (
        <div className="border-t border-slate-100 pt-2">
          <p className="text-[11px] font-medium text-slate-500">Connections</p>
          {Object.entries(node.next).map(([o, t]) => (
            <div key={o} className="flex items-center justify-between text-xs">
              <span>
                <span className="font-medium">{o}</span> → {t}
              </span>
              <button onClick={() => onRemoveEdge(o)} className="text-red-500 hover:underline">
                remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange, placeholder, textarea }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; textarea?: boolean }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      {textarea ? (
        <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="mt-1 h-16 w-full rounded border border-slate-300 px-2 py-1 text-xs" />
      ) : (
        <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-xs" />
      )}
    </label>
  );
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-xs">
        {options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}

function JsonField({ label, value, onChange }: { label: string; value: unknown; onChange: (v: unknown) => void }) {
  const [text, setText] = useState(JSON.stringify(value, null, 2));
  const [bad, setBad] = useState(false);
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          try {
            onChange(JSON.parse(e.target.value));
            setBad(false);
          } catch {
            setBad(true);
          }
        }}
        className={`mt-1 h-28 w-full rounded border px-2 py-1 font-mono text-[11px] ${bad ? "border-red-400 bg-red-50" : "border-slate-300"}`}
      />
    </label>
  );
}
