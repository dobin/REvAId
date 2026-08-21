import { describe, expect, it } from "vitest";
import type { ViewNodeDto } from "@/api/types";
import { deriveCanvasEdges } from "./deriveCanvasEdges";

function makeNode(overrides: Partial<ViewNodeDto> & { functionId: number }): ViewNodeDto {
  return {
    visible: true,
    collapsed: false,
    color: null,
    posX: 0,
    posY: 0,
    pinned: false,
    originFunctionId: null,
    originKind: "root",
    originImplied: false,
    ...overrides,
  };
}

describe("deriveCanvasEdges", () => {
  it("produces no edges for a single root node", () => {
    const nodes = [makeNode({ functionId: 1, originKind: "root", originFunctionId: null })];
    expect(deriveCanvasEdges(nodes)).toEqual([]);
  });

  it("connects a fanout child to its origin parent", () => {
    const nodes = [
      makeNode({ functionId: 1, originKind: "root", originFunctionId: null }),
      makeNode({ functionId: 2, originKind: "fanout", originFunctionId: 1 }),
    ];
    const edges = deriveCanvasEdges(nodes);
    expect(edges).toEqual([
      { id: "1->2", source: 1, target: 2, implied: false, kind: "fanout" },
    ]);
  });

  it("D8b: two independently-placed nodes that call each other produce NO edge", () => {
    // Both nodes are roots (placed independently, e.g. two separate
    // searches) — even if `edges` (caller/callee) says 1 calls 2, provenance
    // says neither originated from the other, so no connector may appear.
    const nodes = [
      makeNode({ functionId: 1, originKind: "root", originFunctionId: null }),
      makeNode({ functionId: 2, originKind: "root", originFunctionId: null }),
    ];
    expect(deriveCanvasEdges(nodes)).toEqual([]);
  });

  it("omits an edge whose origin parent is not present in the input list", () => {
    // e.g. the parent was hidden (visible:false) and the caller only passed
    // visible nodes — the child's connector must vanish, but the child
    // itself still renders as its own node.
    const nodes = [makeNode({ functionId: 2, originKind: "fanout", originFunctionId: 1 })];
    expect(deriveCanvasEdges(nodes)).toEqual([]);
  });

  it("marks a callstack-imported implied link as dashed via `implied`", () => {
    const nodes = [
      makeNode({ functionId: 1, originKind: "root", originFunctionId: null }),
      makeNode({
        functionId: 2,
        originKind: "callstack",
        originFunctionId: 1,
        originImplied: true,
      }),
    ];
    expect(deriveCanvasEdges(nodes)).toEqual([
      { id: "1->2", source: 1, target: 2, implied: true, kind: "callstack" },
    ]);
  });

  it("builds one edge per node with a present origin, in a multi-node chain", () => {
    const nodes = [
      makeNode({ functionId: 1, originKind: "root", originFunctionId: null }),
      makeNode({ functionId: 2, originKind: "fanout", originFunctionId: 1 }),
      makeNode({ functionId: 3, originKind: "fanout", originFunctionId: 2 }),
    ];
    const edges = deriveCanvasEdges(nodes);
    expect(edges).toHaveLength(2);
    expect(edges).toEqual(
      expect.arrayContaining([
        { id: "1->2", source: 1, target: 2, implied: false, kind: "fanout" },
        { id: "2->3", source: 2, target: 3, implied: false, kind: "fanout" },
      ]),
    );
  });
});
