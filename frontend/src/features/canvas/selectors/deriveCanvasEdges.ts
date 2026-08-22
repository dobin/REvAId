/**
 * D8b/T4: canvas edges are derived **exclusively** from `ViewNodeDto.origin_*`
 * — never from the `edges` table. This is the single function responsible
 * for that invariant; nothing else in the frontend may compute a canvas edge.
 *
 * A pure function over the node list passed in: callers control which nodes
 * are "on the canvas" for this purpose by choosing what to pass (e.g. only
 * `visible` nodes) — hiding a parent naturally hides its connector without
 * this function needing to know about visibility itself, and a node whose
 * `originFunctionId` isn't present in the input list produces no edge for
 * that pairing (its child is simply not connected upward), rather than a
 * broken read of the entire list.
 */
import type { CanvasEdge, ViewNodeDto } from "@/api/types";

export function deriveCanvasEdges(nodes: ViewNodeDto[]): CanvasEdge[] {
  const presentFunctionIds = new Set(nodes.map((n) => n.functionId));
  const edges: CanvasEdge[] = [];

  for (const node of nodes) {
    if (node.originFunctionId === null) continue;
    if (!presentFunctionIds.has(node.originFunctionId)) continue;

    // Orientation, not existence, decides left/right (D8b). Every provenance
    // node still records exactly one origin, but a `fanin` node (a fanned-out
    // *caller*) is the *source* of the call, so its edge points from itself
    // *to* the card it was spawned from — ELK (direction RIGHT) then lays a
    // source to the left of its target, placing the caller on the left. Every
    // other kind (`fanout`, `callstack`) points origin -> node, growing right.
    const grewFromCaller = node.originKind === "fanin";
    const source = grewFromCaller ? node.functionId : node.originFunctionId;
    const target = grewFromCaller ? node.originFunctionId : node.functionId;

    edges.push({
      // Keyed on the owning node's pairing (origin + function), not the
      // oriented (source, target), so the id is unique by construction — one
      // provenance row per (view, function) — regardless of orientation.
      id: `${String(node.originFunctionId)}->${String(node.functionId)}`,
      source,
      target,
      implied: node.originImplied,
      kind: node.originKind,
    });
  }

  return edges;
}
