/**
 * ELK layout worker (D11, TAD §2.5). Runs `elkjs`'s `layered` algorithm off
 * the main thread — ELK is a GWT-compiled JS blob that can block for tens of
 * milliseconds, which would otherwise jank the ≤400ms layout animation.
 *
 * Protocol: the main thread posts a {@link LayoutRequest} (with a `requestId`
 * for coalescing/latest-wins on the caller's side) and this worker posts back
 * a {@link LayoutResponse} with the same `requestId` plus computed positions.
 */
import ELK from "elkjs/lib/elk.bundled.js";

export interface LayoutInputNode {
  id: string;
  width: number;
  height: number;
}

export interface LayoutInputEdge {
  id: string;
  source: string;
  target: string;
}

export interface LayoutRequest {
  requestId: number;
  nodes: LayoutInputNode[];
  edges: LayoutInputEdge[];
}

export interface LayoutResponse {
  requestId: number;
  positions: Record<string, { x: number; y: number }>;
}

const elk = new ELK();

self.onmessage = (event: MessageEvent<LayoutRequest>) => {
  const { requestId, nodes, edges } = event.data;

  const graph = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.layered.layering.strategy": "NETWORK_SIMPLEX",
      // §5.1: cycles must not explode — GREEDY cycle breaking handles
      // back-edges (recursion, mutual recursion) without pathological output.
      "elk.layered.cycleBreaking.strategy": "GREEDY",
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
      "elk.spacing.nodeNodeBetweenLayers": "80",
      "elk.spacing.nodeNode": "48",
    },
    children: nodes.map((n) => ({ id: n.id, width: n.width, height: n.height })),
    edges: edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  };

  elk
    .layout(graph)
    .then((laidOut) => {
      const positions: Record<string, { x: number; y: number }> = {};
      for (const child of laidOut.children ?? []) {
        if (child.id && child.x !== undefined && child.y !== undefined) {
          positions[child.id] = { x: child.x, y: child.y };
        }
      }
      const response: LayoutResponse = { requestId, positions };
      self.postMessage(response);
    })
    .catch((_error: unknown) => {
      // A failed layout is a no-op for the caller (nodes keep their current
      // positions) — never crash the worker over one bad request.
      const response: LayoutResponse = { requestId, positions: {} };
      self.postMessage(response);
    });
};
