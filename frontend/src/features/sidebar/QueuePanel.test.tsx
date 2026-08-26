/**
 * Sidebar "LLM Activity" panel: renders in-flight functions with elapsed
 * time and the queued count from the queue cache; renders nothing when the
 * queue is idle.
 */
import { act, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { QueueSnapshotDto } from "@/api/types";
import { QUEUE_QUERY_KEY } from "@/api/queries/queue";
import { QueuePanel } from "./QueuePanel";

function renderWithQueue(snapshot: QueueSnapshotDto | undefined) {
  const qc = new QueryClient();
  if (snapshot) qc.setQueryData(QUEUE_QUERY_KEY, snapshot);
  const result = render(
    <QueryClientProvider client={qc}>
      <QueuePanel />
    </QueryClientProvider>,
  );
  return result;
}

const idle: QueueSnapshotDto = {
  inFlight: [],
  queued: [],
  inFlightCount: 0,
  queuedCount: 0,
  pausedUntil: null,
};

describe("QueuePanel", () => {
  it("renders nothing when the queue is idle", () => {
    const { container } = renderWithQueue(idle);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing with no cached data yet", () => {
    const { container } = renderWithQueue(undefined);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists in-flight functions and the queued count", () => {
    renderWithQueue({
      inFlight: [
        { functionId: 17, displayName: "parse_header", startedAt: null },
        { functionId: 23, displayName: "eval_expr", startedAt: null },
      ],
      queued: [
        { functionId: 25, displayName: "FUN_00003000", priority: 1 },
        { functionId: 40, displayName: "FUN_00004000", priority: 2 },
      ],
      inFlightCount: 2,
      queuedCount: 2,
      pausedUntil: null,
    });
    expect(screen.getByText("parse_header")).toBeInTheDocument();
    expect(screen.getByText("eval_expr")).toBeInTheDocument();
    expect(screen.getByText(/2 analysing, 2 queued/)).toBeInTheDocument();
  });

  it("caps the in-flight list and shows an overflow note", () => {
    renderWithQueue({
      inFlight: Array.from({ length: 7 }, (_, i) => ({
        functionId: i,
        displayName: `fn_${i}`,
        startedAt: null,
      })),
      queued: [],
      inFlightCount: 7,
      queuedCount: 0,
      pausedUntil: null,
    });
    expect(screen.getByText("fn_0")).toBeInTheDocument();
    expect(screen.getByText("fn_4")).toBeInTheDocument();
    expect(screen.queryByText("fn_5")).not.toBeInTheDocument();
    expect(screen.getByText("+2 more…")).toBeInTheDocument();
  });

  it("shows the paused note when rate-limited", () => {
    renderWithQueue({
      inFlight: [{ functionId: 17, displayName: "parse_header", startedAt: null }],
      queued: [],
      inFlightCount: 1,
      queuedCount: 0,
      pausedUntil: "2026-08-26T00:01:00Z",
    });
    expect(screen.getByText(/rate-limited, paused/)).toBeInTheDocument();
  });

  it("elapsed time ticks up while a function is in flight", () => {
    // Freeze time, then advance it manually — the panel must re-render on
    // its own 1s interval and show the new elapsed label.
    const start = Date.parse("2026-08-26T00:00:00Z");
    vi.useFakeTimers();
    vi.setSystemTime(start);
    try {
      renderWithQueue({
        inFlight: [
          { functionId: 17, displayName: "parse_header", startedAt: "2026-08-26T00:00:00Z" },
        ],
        queued: [],
        inFlightCount: 1,
        queuedCount: 0,
        pausedUntil: null,
      });
      expect(screen.getByText("0s")).toBeInTheDocument();

      vi.setSystemTime(start + 3500);
      act(() => {
        vi.advanceTimersByTime(1000);
      });

      // 3.5s of system time + the 1s the timer advance itself simulates.
      expect(screen.getByText("4s")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
