/**
 * Cache patching for incoming SSE events (TAD §4.3 "one event, all
 * surfaces", E5a/E5b). `applySummaryEvent` is exactly the TAD's own sketch:
 * one `summary` event patches both the function-detail cache entry AND the
 * matching row in every cached neighbour page — no refetch, no ELK re-run
 * (T1: card geometry derives from row count, known before any summary
 * exists; summaries must never trigger a layout pass).
 */
import type { QueryClient } from "@tanstack/react-query";
import type {
  FunctionDto,
  NeighbourPageDto,
  QueueEvent,
  QueueSnapshotDto,
  ServerEvent,
  SummaryEvent,
} from "@/api/types";
import { QUEUE_QUERY_KEY } from "@/api/queries/queue";

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
  // `NeighbourRowDto` carries no `nameAnalyst`, but `isRenamed` gates the
  // LLM name server-side (analyst beats LLM), so a renamed row keeps its
  // analyst display name untouched.
  qc.setQueriesData<NeighbourPageDto>({ queryKey: ["neighbours"] }, (page) =>
    page && page.rows.some((r) => r.id === e.functionId)
      ? {
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
        }
      : page,
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
