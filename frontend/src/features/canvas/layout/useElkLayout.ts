/**
 * `useElkLayout` (D11, D15, TAD §2.5) — runs the ELK worker for the
 * non-pinned subset of nodes, request-coalesced with latest-wins semantics
 * (a superseding call's response is honored; a stale response for an
 * already-superseded `requestId` is ignored).
 *
 * Pinned nodes (D15: manual drag sets `pinned = true` permanently) are
 * never sent to ELK and never repositioned by this hook — the caller must
 * keep their existing positions as-is.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { LayoutInputEdge, LayoutInputNode, LayoutRequest, LayoutResponse } from "./elk.worker";

export interface ElkLayoutNode extends LayoutInputNode {
  pinned: boolean;
}

export type ElkWorkerFactory = () => Worker;

const defaultWorkerFactory: ElkWorkerFactory = () =>
  new Worker(new URL("./elk.worker.ts", import.meta.url), { type: "module" });

export function useElkLayout(workerFactory: ElkWorkerFactory = defaultWorkerFactory) {
  const workerRef = useRef<Worker | null>(null);
  const requestIdRef = useRef(0);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});

  useEffect(() => {
    let worker: Worker;
    try {
      worker = workerFactory();
    } catch {
      // jsdom (unit tests using the default factory) has no Web Worker
      // global — skip wiring one up rather than crashing; `runLayout`
      // becomes a no-op in that environment. A test-injected factory
      // (fake worker) never throws here, so this only affects the default.
      return;
    }
    workerRef.current = worker;

    worker.onmessage = (event: MessageEvent<LayoutResponse>) => {
      // Latest-wins: ignore a response for any request that isn't the most
      // recently issued one (a superseded, in-flight request resolving late).
      if (event.data.requestId !== requestIdRef.current) return;
      setPositions(event.data.positions);
    };

    return () => {
      worker.terminate();
      workerRef.current = null;
    };
  }, [workerFactory]);

  const runLayout = useCallback((nodes: ElkLayoutNode[], edges: LayoutInputEdge[]) => {
    const worker = workerRef.current;
    if (!worker) return;

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    const unpinned = nodes.filter((n) => !n.pinned);
    const unpinnedIds = new Set(unpinned.map((n) => n.id));
    // Only edges between two unpinned nodes are meaningful to ELK's layout
    // (a pinned node is a fixed obstacle, not a layout participant).
    const relevantEdges = edges.filter(
      (e) => unpinnedIds.has(e.source) && unpinnedIds.has(e.target),
    );

    const request: LayoutRequest = {
      requestId,
      nodes: unpinned.map(({ id, width, height }) => ({ id, width, height })),
      edges: relevantEdges,
    };
    worker.postMessage(request);
  }, []);

  return { positions, runLayout };
}
