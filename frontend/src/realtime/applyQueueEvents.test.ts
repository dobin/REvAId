/**
 * Queue SSE event patching: worker-driven events carry the full per-item
 * `inFlight`/`queued` lists (the sidebar "LLM Activity" panel's data), while
 * counter-only events from demand mutations must leave the cached lists
 * untouched.
 */
import { QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { QueueSnapshotDto } from "@/api/types";
import { QUEUE_QUERY_KEY } from "@/api/queries/queue";
import { applyQueueEvent } from "./applyEvents";

let qc: QueryClient;

beforeEach(() => {
  qc = new QueryClient();
});

afterEach(() => {
  qc.clear();
});

function makeSnapshot(): QueueSnapshotDto {
  return {
    inFlight: [
      { functionId: 17, displayName: "FUN_00001000", startedAt: "2026-08-26T00:00:00Z" },
    ],
    queued: [{ functionId: 18, displayName: "FUN_00002000", priority: 1 }],
    inFlightCount: 1,
    queuedCount: 1,
    pausedUntil: null,
  };
}

describe("applyQueueEvent per-item patching", () => {
  it("a worker-driven event replaces the inFlight/queued lists", () => {
    qc.setQueryData(QUEUE_QUERY_KEY, makeSnapshot());
    applyQueueEvent(qc, {
      type: "queue",
      inFlightCount: 2,
      queuedCount: 0,
      pausedUntil: null,
      inFlight: [
        { functionId: 17, displayName: "parse_header", startedAt: null },
        { functionId: 23, displayName: "eval_expr", startedAt: null },
      ],
      queued: [],
    });
    const snapshot = qc.getQueryData<QueueSnapshotDto>(QUEUE_QUERY_KEY);
    expect(snapshot?.inFlightCount).toBe(2);
    expect(snapshot?.queuedCount).toBe(0);
    expect(snapshot?.inFlight).toHaveLength(2);
    expect(snapshot?.inFlight[0]?.displayName).toBe("parse_header");
    expect(snapshot?.queued).toHaveLength(0);
  });

  it("a counter-only event refreshes counts but keeps the cached lists", () => {
    qc.setQueryData(QUEUE_QUERY_KEY, makeSnapshot());
    applyQueueEvent(qc, {
      type: "queue",
      inFlightCount: 3,
      queuedCount: 5,
      pausedUntil: null,
    });
    const snapshot = qc.getQueryData<QueueSnapshotDto>(QUEUE_QUERY_KEY);
    expect(snapshot?.inFlightCount).toBe(3);
    expect(snapshot?.queuedCount).toBe(5);
    // Lists untouched — the stale entries remain until the next full event.
    expect(snapshot?.inFlight).toHaveLength(1);
    expect(snapshot?.queued).toHaveLength(1);
  });
});
