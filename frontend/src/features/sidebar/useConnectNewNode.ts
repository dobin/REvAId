/**
 * Resolves the provenance (`originFunctionId` + `originKind`) for a function
 * being placed onto the canvas via the sidebar "Add function" flow, so that a
 * newly-added function connects to an already-on-canvas function it has a call
 * relationship with — mirroring the behaviour of fan-out (⤢) rather than
 * always landing as a disconnected `root` node.
 *
 * Why this is safe / in-spec (TAD T4/D8b): canvas edges are derived
 * *exclusively* from `view_nodes.origin_*` by `deriveCanvasEdges`. We do not
 * touch the `edges` table on the client; we only reuse the `onCanvas` flag
 * that `GET /functions/{id}/neighbours` already returns per row. Emitting
 * `{originFunctionId, originKind}` together also satisfies the backend
 * `canvas_service` invariant (a non-root origin must carry an origin id).
 *
 * Orientation (from `deriveCanvasEdges` + `CanvasView.fanOutFunction`):
 *  - The new function N is *called by* an on-canvas function X (X is a parent
 *    / caller). X → N should grow rightward ⇒ `originKind: "fanout"`,
 *    `originFunctionId: X`. Discovered via N's *callers* page: a row whose
 *    id is on-canvas is a caller of N.
 *  - The new function N *calls* an on-canvas function X (X is a callee). The
 *    edge N → X should place N to the left ⇒ `originKind: "fanin"`,
 *    `originFunctionId: X`. Discovered via N's *callees* page: a row whose id
 *    is on-canvas is a callee of N.
 *
 * We prefer linking to a caller (parent) so the new node grows to the right of
 * an existing parent, matching the fan-out intuition; if no caller is on the
 * canvas we fall back to a callee, and if neither, to a disconnected `root`.
 */
import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { neighbourQueryOptions } from "@/api/queries/neighbours";
import type { FunctionId, OriginKind, ViewId } from "@/api/types";

export interface NewNodeOrigin {
  originFunctionId: FunctionId;
  originKind: OriginKind;
}

/**
 * Returns a resolver that, given a function id, discovers a single connected
 * on-canvas function to attach it to, or `null` when there is no on-canvas
 * connection (caller should then place the node as `root`).
 *
 * `callersSuppressed` (very high fan-in) can hide caller connections; in that
 * case we silently fall back to the callee direction, and ultimately to
 * `root` — a rare missed link, never a wrong one.
 */
export function useConnectNewNode(viewId: ViewId | null) {
  const queryClient = useQueryClient();

  return useCallback(
    async (functionId: FunctionId): Promise<NewNodeOrigin | null> => {
      if (viewId === null) return null;

      const baseParams = {
        functionId,
        viewId,
        group: "primary",
        sort: "name",
        order: "asc",
      } as const;

      // Prefer a caller (parent): N grows to the right of an existing parent.
      // Fetch both directions; the callers page may be suppressed, in which
      // case its `rows` is empty and we simply consider the callees instead.
      const [callers, callees] = await Promise.all([
        queryClient
          .fetchQuery(neighbourQueryOptions({ ...baseParams, direction: "callers" }))
          .catch(() => null),
        queryClient
          .fetchQuery(neighbourQueryOptions({ ...baseParams, direction: "callees" }))
          .catch(() => null),
      ]);

      const onCanvasCaller = callers?.rows.find(
        (r) => r.onCanvas && !r.isSelf,
      );
      if (onCanvasCaller) {
        // X (caller) → N : grows right.
        return { originFunctionId: onCanvasCaller.id, originKind: "fanout" };
      }

      const onCanvasCallee = callees?.rows.find(
        (r) => r.onCanvas && !r.isSelf,
      );
      if (onCanvasCallee) {
        // N → X (callee) : N placed to the left of X.
        return { originFunctionId: onCanvasCallee.id, originKind: "fanin" };
      }

      return null;
    },
    [queryClient, viewId],
  );
}
