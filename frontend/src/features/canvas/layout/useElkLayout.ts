/**
 * `useElkLayout` (D11, D15, TAD §2.5) — runs ELK layout for the non-pinned
 * subset of nodes, request-coalesced with latest-wins semantics (a
 * superseding call's result is honored; a stale result for an
 * already-superseded request is discarded once it resolves).
 *
 * Pinned nodes (D15: manual drag sets `pinned = true` permanently) are
 * never sent to ELK and never repositioned by this hook — the caller must
 * keep their existing positions as-is.
 */
import { useCallback, useRef, useState } from "react";
import type { LayoutInputEdge, LayoutInputNode, LayoutPositions } from "./elkLayout";
import { computeElkLayout } from "./elkLayout";

export interface ElkLayoutNode extends LayoutInputNode {
  pinned: boolean;
  /** Current canvas position. Required for a pinned node (it becomes a fixed
   * obstacle the laid-out block must clear); ignored for an unpinned one,
   * whose position is ELK's job to decide. */
  x?: number;
  y?: number;
}

export type ElkLayoutFn = typeof computeElkLayout;

export function useElkLayout(layoutFn: ElkLayoutFn = computeElkLayout) {
  const requestIdRef = useRef(0);
  const [positions, setPositions] = useState<LayoutPositions>({});

  const runLayout = useCallback(
    (nodes: ElkLayoutNode[], edges: LayoutInputEdge[]) => {
      const requestId = requestIdRef.current + 1;
      requestIdRef.current = requestId;

      const unpinned = nodes.filter((n) => !n.pinned);
      const unpinnedIds = new Set(unpinned.map((n) => n.id));
      // Only edges between two unpinned nodes are meaningful to ELK's layout
      // (a pinned node is a fixed obstacle, not a layout participant).
      const relevantEdges = edges.filter(
        (e) => unpinnedIds.has(e.source) && unpinnedIds.has(e.target),
      );
      // A pinned node is excluded from the graph (D15 — ELK must never move
      // it) but is still physically on the canvas, so it has to be passed
      // along as an obstacle. Otherwise ELK lays the unpinned block out from
      // its own origin and the result lands on top of the pinned card.
      const obstacles = nodes
        .filter((n) => n.pinned && n.x !== undefined && n.y !== undefined)
        .map((n) => ({ x: n.x ?? 0, y: n.y ?? 0, width: n.width, height: n.height }));

      void layoutFn(
        unpinned.map(({ id, width, height }) => ({ id, width, height })),
        relevantEdges,
        obstacles,
      ).then((result) => {
        // Latest-wins: ignore a result for any request that isn't the most
        // recently issued one (a superseded, in-flight call resolving late).
        if (requestId !== requestIdRef.current) return;
        setPositions(result);
      });
    },
    [layoutFn],
  );

  return { positions, runLayout };
}
