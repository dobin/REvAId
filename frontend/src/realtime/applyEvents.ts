/**
 * Cache patching for incoming SSE events (TAD §4.3 "one event, all
 * surfaces", E5a/E5b). `applySummaryEvent` is exactly the TAD's own sketch:
 * one `summary` event patches both the function-detail cache entry AND the
 * matching row in every cached neighbour page — no refetch, no ELK re-run
 * (T1: card geometry derives from row count, known before any summary
 * exists; summaries must never trigger a layout pass).
 */
import type { InfiniteData, QueryClient } from "@tanstack/react-query";
import type {
  FunctionDto,
  NeighbourPageDto,
  QueueEvent,
  QueueSnapshotDto,
  ServerEvent,
  SummaryEvent,
} from "@/api/types";
import { QUEUE_QUERY_KEY } from "@/api/queries/queue";

/**
 * Patch a single neighbour page's rows for one summary event. Shared by the
 * bare-page cache (`useNeighboursQuery`, key `["neighbours", ...]`) and the
 * paginated cache (`useInfiniteNeighboursQuery`, key
 * `["neighbours-infinite", ...]`) — the card tables use the latter, so
 * patching only the former (the original bug) left row names showing `FUN_…`
 * until a manual reload.
 *
 * `NeighbourRowDto` carries no `nameAnalyst`, but `isRenamed` gates the LLM
 * name server-side (analyst beats LLM), so a renamed row keeps its analyst
 * display name untouched.
 */
function patchNeighbourPage(page: NeighbourPageDto, e: SummaryEvent): NeighbourPageDto {
  if (!page.rows.some((r) => r.id === e.functionId)) return page;
  return {
    ...page,
    rows: page.rows.map((r) =>
      r.id === e.functionId
        ? {
            ...r,
            nameLlm: e.nameLlm ?? r.nameLlm,
            displayName: !r.isRenamed && e.nameLlm ? e.nameLlm : r.displayName,
            summaryShort: e.summaryShort ?? r.summaryShort,
            summaryStatus: e.summaryStatus,
            summaryLowConfidence: e.lowConfidence,
          }
        : r,
    ),
  };
}

export function applySummaryEvent(qc: QueryClient, e: SummaryEvent): void {
  qc.setQueryData<FunctionDto>(["function", e.functionId], (fn) =>
    fn
      ? {
          ...fn,
          // C13 auto-display: patch the proposed name and recompute the
          // display name with the same precedence the server applies
          // (`name_analyst ?? name_llm ?? name_ghidra`) — E5a "one event,
          // all surfaces", no refetch, no reload.
          nameLlm: e.nameLlm ?? fn.nameLlm,
          displayName: fn.nameAnalyst ?? e.nameLlm ?? fn.nameGhidra,
          summary: {
            ...fn.summary,
            status: e.summaryStatus,
            short: e.summaryShort ?? fn.summary.short,
            model: e.summaryModel ?? fn.summary.model,
            errorCode: e.errorCode,
            lowConfidence: e.lowConfidence,
            generatedAt: e.generatedAt ?? fn.summary.generatedAt,
            isStale: e.summaryStatus === "stale",
          },
        }
      : fn,
  );

  // Patch the row wherever it appears, in every cached neighbour page —
  // this is the "one event updates all surfaces" requirement (E5a): the
  // same function can be a row in several open cards' tables at once.
  //
  // Two distinct caches hold neighbour rows and BOTH must be patched:
  //  - `["neighbours", ...]`         — `useNeighboursQuery` (single page).
  //  - `["neighbours-infinite", ...]` — `useInfiniteNeighboursQuery`, whose
  //    value is `InfiniteData<NeighbourPageDto>` (`{ pages: [...] }`), NOT a
  //    bare page. The card tables (`NeighbourTable`) use THIS one; a prefix
  //    match on `["neighbours"]` does not reach the `-infinite` key, so it
  //    was silently skipped before (the reason row names only fixed on
  //    reload). Note the `exact: false` default still won't cross the
  //    differing first key segment, hence two explicit `setQueriesData`.
  qc.setQueriesData<NeighbourPageDto>({ queryKey: ["neighbours"] }, (page) =>
    page ? patchNeighbourPage(page, e) : page,
  );
  qc.setQueriesData<InfiniteData<NeighbourPageDto>>(
    { queryKey: ["neighbours-infinite"] },
    (data) =>
      data
        ? { ...data, pages: data.pages.map((page) => patchNeighbourPage(page, e)) }
        : data,
  );
}

export function applyQueueEvent(qc: QueryClient, e: QueueEvent): void {
  qc.setQueryData<QueueSnapshotDto>(QUEUE_QUERY_KEY, (snapshot) =>
    snapshot
      ? {
          ...snapshot,
          inFlightCount: e.inFlightCount,
          queuedCount: e.queuedCount,
          pausedUntil: e.pausedUntil,
          // Worker-driven events carry the full per-item lists (the
          // sidebar's "thinking" panel reads these); counter-only events
          // from demand mutations leave the cached lists untouched.
          ...(e.inFlight !== undefined ? { inFlight: e.inFlight } : {}),
          ...(e.queued !== undefined ? { queued: e.queued } : {}),
        }
      : snapshot,
  );
}

/**
 * Reconnect reconciliation (TAD §2.7/§4.3): never trust client memory across
 * a gap. Invalidates every surface an SSE event can patch, plus refetches
 * the queue snapshot, so a dropped connection (overflow `reconcile`, or a
 * plain `EventSource` `error` → `open` cycle) always re-reads authoritative
 * server state rather than leaving a stale `pending`/`ready` badge on screen.
 */
export function reconcileAfterReconnect(qc: QueryClient): void {
  void qc.invalidateQueries({ queryKey: ["function"] });
  void qc.invalidateQueries({ queryKey: ["neighbours"] });
  // Separate key segment ("neighbours-infinite") — not covered by the
  // "neighbours" invalidation's prefix match, so invalidate it explicitly.
  void qc.invalidateQueries({ queryKey: ["neighbours-infinite"] });
  void qc.invalidateQueries({ queryKey: QUEUE_QUERY_KEY });
}

/** Dispatch one already-decoded `ServerEvent` to the right cache patcher. */
export function applyServerEvent(qc: QueryClient, event: ServerEvent): void {
  switch (event.type) {
    case "summary":
      applySummaryEvent(qc, event);
      return;
    case "queue":
      applyQueueEvent(qc, event);
      return;
    case "reconcile":
      reconcileAfterReconnect(qc);
      return;
    case "binary":
      // Binary lifecycle (ingestion completed / binary deleted) — the
      // binaries list is cheap to refetch outright rather than patch.
      void qc.invalidateQueries({ queryKey: ["binaries"] });
      return;
    default:
      return;
  }
}
