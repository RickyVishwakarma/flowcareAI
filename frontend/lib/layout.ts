/**
 * Layered graph layout: assign each node a column by its BFS depth from the
 * trigger, then stack nodes within a column into rows. Pure + deterministic so
 * it can be unit-tested and shared between the editor and the read-only canvas.
 */

export interface LayoutNode {
  node_key: string;
  kind: string;
  next: Record<string, string>;
}

export interface LayoutOptions {
  colWidth: number;
  rowGap: number;
  pad: number;
}

/** Map of node_key → column depth (trigger = 0). Unreachable nodes go last. */
export function assignDepths(nodes: LayoutNode[]): Map<string, number> {
  const byKey = new Map(nodes.map((n) => [n.node_key, n]));
  const depth = new Map<string, number>();
  if (nodes.length === 0) return depth;

  const root = nodes.find((n) => n.kind === "trigger") ?? nodes[0];
  const queue: [string, number][] = [[root.node_key, 0]];
  while (queue.length) {
    const [key, d] = queue.shift()!;
    if (depth.has(key)) continue;
    depth.set(key, d);
    const node = byKey.get(key);
    if (!node) continue;
    for (const target of Object.values(node.next)) {
      if (target && byKey.has(target) && !depth.has(target)) queue.push([target, d + 1]);
    }
  }
  // Nodes not reachable from the trigger get parked in a trailing column.
  const maxDepth = depth.size ? Math.max(...depth.values()) : 0;
  for (const n of nodes) {
    if (!depth.has(n.node_key)) depth.set(n.node_key, maxDepth + 1);
  }
  return depth;
}

/** Map of node_key → {x, y} pixel position. */
export function layeredLayout(
  nodes: LayoutNode[],
  { colWidth, rowGap, pad }: LayoutOptions,
): Map<string, { x: number; y: number }> {
  const depth = assignDepths(nodes);
  const rowCursor = new Map<number, number>();
  const positions = new Map<string, { x: number; y: number }>();
  for (const n of nodes) {
    const d = depth.get(n.node_key) ?? 0;
    const row = rowCursor.get(d) ?? 0;
    rowCursor.set(d, row + 1);
    positions.set(n.node_key, { x: pad + d * colWidth, y: pad + row * rowGap });
  }
  return positions;
}
