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

    edges.push({
      id: `${String(node.originFunctionId)}->${String(node.functionId)}`,
      source: node.originFunctionId,
      target: node.functionId,
      implied: node.originImplied,
      kind: node.originKind,
    });
  }

  return edges;
}
