"use client";

import { useMemo } from "react";
import type { WorkflowNode } from "@/lib/api";

const KIND_STYLE: Record<string, string> = {
  trigger: "border-violet-300 bg-violet-50",
  condition: "border-amber-300 bg-amber-50",
  action: "border-sky-300 bg-sky-50",
};

const COL_W = 230;
const ROW_H = 92;
const NODE_W = 180;
const NODE_H = 56;

interface Placed extends WorkflowNode {
  x: number;
  y: number;
}

/** Auto-layout: BFS from the trigger to assign columns, stack siblings in rows. */
function layout(nodes: WorkflowNode[]): { placed: Placed[]; width: number; height: number } {
  const byKey = new Map(nodes.map((n) => [n.node_key, n]));
  const depth = new Map<string, number>();
  const root = nodes.find((n) => n.kind === "trigger") ?? nodes[0];
  if (!root) return { placed: [], width: 0, height: 0 };

  const queue: [string, number][] = [[root.node_key, 0]];
  while (queue.length) {
    const [key, d] = queue.shift()!;
    if (depth.has(key)) continue;
    depth.set(key, d);
    const node = byKey.get(key);
    if (!node) continue;
    for (const next of Object.values(node.next)) {
      if (next && byKey.has(next)) queue.push([next, d + 1]);
    }
  }
  // Unreached nodes go in a trailing column.
  const maxDepth = Math.max(0, ...depth.values());
  nodes.forEach((n) => {
    if (!depth.has(n.node_key)) depth.set(n.node_key, maxDepth + 1);
  });

  const rowCursor = new Map<number, number>();
  const placed: Placed[] = nodes.map((n) => {
    const d = depth.get(n.node_key) ?? 0;
    const row = rowCursor.get(d) ?? 0;
    rowCursor.set(d, row + 1);
    return { ...n, x: d * COL_W + 20, y: row * ROW_H + 20 };
  });

  const width = (Math.max(0, ...placed.map((p) => p.x)) || 0) + NODE_W + 40;
  const height = (Math.max(0, ...placed.map((p) => p.y)) || 0) + NODE_H + 40;
  return { placed, width, height };
}

export function WorkflowCanvas({ nodes }: { nodes: WorkflowNode[] }) {
  const { placed, width, height } = useMemo(() => layout(nodes), [nodes]);
  const pos = useMemo(() => new Map(placed.map((p) => [p.node_key, p])), [placed]);

  if (placed.length === 0) {
    return <p className="text-sm text-slate-400">This workflow has no nodes yet.</p>;
  }

  return (
    <div className="overflow-auto rounded-md border border-white/10 bg-white/5" style={{ maxHeight: 520 }}>
      <div className="relative" style={{ width, height }}>
        <svg className="absolute inset-0" width={width} height={height}>
          {placed.flatMap((node) =>
            Object.entries(node.next).map(([label, target]) => {
              const to = pos.get(target);
              if (!to) return null;
              const x1 = node.x + NODE_W;
              const y1 = node.y + NODE_H / 2;
              const x2 = to.x;
              const y2 = to.y + NODE_H / 2;
              const mx = (x1 + x2) / 2;
              return (
                <g key={`${node.node_key}-${label}-${target}`}>
                  <path
                    d={`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`}
                    fill="none"
                    stroke="#94a3b8"
                    strokeWidth={1.5}
                  />
                  {label !== "default" && (
                    <text x={mx} y={(y1 + y2) / 2 - 4} fill="#64748b" fontSize={10} textAnchor="middle">
                      {label}
                    </text>
                  )}
                </g>
              );
            }),
          )}
        </svg>

        {placed.map((node) => (
          <div
            key={node.node_key}
            className={`absolute rounded-md border px-3 py-2 shadow-sm ${KIND_STYLE[node.kind] ?? "border-white/15 bg-surface"}`}
            style={{ left: node.x, top: node.y, width: NODE_W, height: NODE_H }}
          >
            <p className="text-[10px] uppercase tracking-wide text-slate-400">{node.kind}</p>
            <p className="truncate text-sm font-medium">{node.type}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
