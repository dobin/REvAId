/**
 * I9 auto-demand trigger (PLAN-I7-I8-I9-I13 §5.3). Bridges the pure
 * `demandSlice` refcount registry to the actual `POST`/`DELETE
 * /functions/{id}/summary` calls (`api/queries/summaries.ts`).
 *
 * Call this from every surface that wants a function's summary kept warm
 * while mounted: `VirtualRowList` (table rows, priority 1/2/3),
 * `FunctionCardNode`/`DetailPanel` (a card's own summary, priority 0).
 *
 * Cost-control rules encoded here (§5.4 exit tests):
 * - `functionIds` is debounced by `config.summaryDemandDebounceMs` before
 *   being committed to the registry — the fast-scroll guard. A function
 *   that only flickers through the overscan window during a fast scroll
 *   never reaches the registry, so it is never requested.
 * - Ids already `ready` or `pending` in the TanStack Query cache are never
 *   re-requested — SSE (I8) keeps that cache current, so a function
 *   requested by an earlier-mounted surface is free for every later one.
 * - `enabled: false` acquires nothing at all (suppressed caller tables,
 *   collapsed utility groups — the surface simply never calls this with
 *   `enabled: true`, so C2b/D7/E2a are enforced by the *caller*, not here).
 * - Unmount releases this surface's demand unconditionally.
 */
import { useEffect, useMemo, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { FunctionDto, FunctionId, NeighbourPageDto, Priority } from "@/api/types";
import { useConfig } from "@/config/ConfigProvider";
import { useAppStore } from "@/store";
import type { SurfaceId } from "@/store/demandSlice";
import { useDebouncedValue } from "./useDebouncedValue";
import {
  useDemandSummaryMutation,
  useReleaseSummaryDemandMutation,
} from "@/api/queries/summaries";

/** True if this function id's summary is already settled/in-flight enough
 * that re-demanding it would be pointless. Checks the function detail cache
 * first (authoritative), then falls back to any cached neighbours page's row
 * for the same id (covers ids never individually fetched). */
function isAlreadySettled(
  queryClient: ReturnType<typeof useQueryClient>,
  functionId: FunctionId,
): boolean {
  const fn = queryClient.getQueryData<FunctionDto>(["function", functionId]);
  if (fn) {
    return fn.summary.status === "ready" || fn.summary.status === "pending";
  }

  const neighbourCaches = queryClient.getQueriesData<NeighbourPageDto>({
    queryKey: ["neighbours"],
  });
  for (const [, page] of neighbourCaches) {
    const row = page?.rows.find((r) => r.id === functionId);
    if (row) {
      return row.summaryStatus === "ready" || row.summaryStatus === "pending";
    }
  }
  return false;
}

export function useSummaryDemand({
  surface,
  functionIds,
  priority,
  enabled = true,
}: {
  /** Stable identifier for this mounted surface (e.g. `card:42`,
   * `table:42:callees:primary`). Must be stable across renders. */
  surface: SurfaceId;
  functionIds: readonly FunctionId[];
  priority: Priority;
  enabled?: boolean;
}) {
  const config = useConfig();
  const queryClient = useQueryClient();
  const acquireDemand = useAppStore((s) => s.acquireDemand);
  const releaseSurface = useAppStore((s) => s.releaseSurface);
  const demandMutation = useDemandSummaryMutation();
  const releaseMutation = useReleaseSummaryDemandMutation();

  // Stringify+sort so the debounce hook (reference-equality on its `value`
  // dep) doesn't restart its timer every render just because the caller
  // passed a fresh array with the same contents.
  const idsKey = useMemo(() => [...functionIds].sort((a, b) => a - b).join(","), [functionIds]);
  const debouncedIdsKey = useDebouncedValue(enabled ? idsKey : "", config.summaryDemandDebounceMs);

  // Keep latest mutation functions in refs so the effect below doesn't need
  // them as deps (mutation objects are not stable across renders).
  const demandRef = useRef(demandMutation.mutate);
  demandRef.current = demandMutation.mutate;
  const releaseRef = useRef(releaseMutation.mutate);
  releaseRef.current = releaseMutation.mutate;

  useEffect(() => {
    const ids = debouncedIdsKey === "" ? [] : debouncedIdsKey.split(",").map(Number);
    const { newlyDemanded, newlyReleased } = acquireDemand(ids, surface);

    for (const functionId of newlyDemanded) {
      if (isAlreadySettled(queryClient, functionId)) continue;
      demandRef.current({ functionId, priority });
    }
    for (const functionId of newlyReleased) {
      releaseRef.current(functionId);
    }
    // priority intentionally excluded: a change in priority for an
    // already-demanded id is out of scope for I9 (no priority-upgrade path
    // client-side; the backend queue already upgrades priority server-side
    // per TAD §2.6 if re-demanded at a higher one).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedIdsKey, surface, acquireDemand, queryClient]);

  // Unconditional release on unmount, regardless of `enabled`/debounce state.
  useEffect(() => {
    return () => {
      const { newlyReleased } = releaseSurface(surface);
      for (const functionId of newlyReleased) {
        releaseRef.current(functionId);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [surface, releaseSurface]);
}
