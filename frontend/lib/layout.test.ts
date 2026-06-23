import { describe, expect, it } from "vitest";
import { assignDepths, layeredLayout, type LayoutNode } from "./layout";

const graph: LayoutNode[] = [
  { node_key: "t", kind: "trigger", next: { default: "c" } },
  { node_key: "c", kind: "condition", next: { true: "a1", false: "a2" } },
  { node_key: "a1", kind: "action", next: {} },
  { node_key: "a2", kind: "action", next: {} },
  { node_key: "orphan", kind: "action", next: {} }, // unreachable from trigger
];

describe("assignDepths", () => {
  it("assigns BFS depth from the trigger", () => {
    const d = assignDepths(graph);
    expect(d.get("t")).toBe(0);
    expect(d.get("c")).toBe(1);
    expect(d.get("a1")).toBe(2);
    expect(d.get("a2")).toBe(2);
  });

  it("parks unreachable nodes in a trailing column", () => {
    const d = assignDepths(graph);
    expect(d.get("orphan")).toBe(3); // maxReached(2) + 1
  });

  it("handles an empty graph", () => {
    expect(assignDepths([]).size).toBe(0);
  });

  it("falls back to the first node when there is no trigger", () => {
    const d = assignDepths([
      { node_key: "x", kind: "action", next: { default: "y" } },
      { node_key: "y", kind: "action", next: {} },
    ]);
    expect(d.get("x")).toBe(0);
    expect(d.get("y")).toBe(1);
  });
});

describe("layeredLayout", () => {
  const pos = layeredLayout(graph, { colWidth: 100, rowGap: 50, pad: 10 });

  it("places the trigger at the padding origin", () => {
    expect(pos.get("t")).toEqual({ x: 10, y: 10 });
  });

  it("aligns same-depth nodes in one column, stacked by row", () => {
    const a1 = pos.get("a1")!;
    const a2 = pos.get("a2")!;
    expect(a1.x).toBe(a2.x); // same column (depth 2)
    expect(a1.x).toBe(10 + 2 * 100);
    expect(a2.y).toBe(a1.y + 50); // next row down
  });
});
