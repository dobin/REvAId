/**
 * Toolbar summary-queue chip (`◌ 3 of 12`) + cancel-pending popover
 * (TAD §4.2 endpoints 20-21, docs/specs/PLAN-I7-I8-I9-I13.md §4.2). Its
 * `GET /queue` cache entry is kept live by `SseProvider` patching in place
 * on every `queue` SSE event (E5b) — this component itself is a plain
 * consumer, no polling logic of its own beyond `useQueueQuery`'s fallback
 * refetch interval.
 */
import { useState } from "react";
import { Spinner } from "@/components/Spinner";
import { useCancelPendingMutation, useQueueQuery } from "@/api/queries/queue";

export function QueueChip() {
  const { data } = useQueueQuery();
  const [open, setOpen] = useState(false);
  const cancelPending = useCancelPendingMutation();

  const inFlight = data?.inFlightCount ?? 0;
  const queued = data?.queuedCount ?? 0;
  const total = inFlight + queued;

  if (total === 0) return null;

  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-label={`Summary queue: ${inFlight} in flight of ${total} total`}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.25rem",
          fontSize: "0.75rem",
          padding: "0.125rem 0.5rem",
          borderRadius: "999px",
          border: "1px solid #d1d5db",
          background: data?.pausedUntil ? "#fef3c7" : "white",
          cursor: "pointer",
        }}
      >
        <Spinner label="Summary generating" /> {inFlight} of {total}
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Summary queue"
          style={{
            position: "absolute",
            top: "100%",
            right: 0,
            marginTop: "0.25rem",
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "0.375rem",
            padding: "0.5rem",
            minWidth: "12rem",
            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
            zIndex: 10,
          }}
        >
          <p style={{ margin: "0 0 0.375rem", fontSize: "0.75rem" }}>
            {inFlight} in flight, {queued} queued
            {data?.pausedUntil && (
              <>
                <br />
                <span style={{ color: "#b45309" }}>Rate-limited — paused.</span>
              </>
            )}
          </p>
          <button
            type="button"
            onClick={() => cancelPending.mutate()}
            disabled={queued === 0 || cancelPending.isPending}
            style={{
              fontSize: "0.75rem",
              padding: "0.25rem 0.5rem",
              border: "1px solid #d1d5db",
              borderRadius: "0.25rem",
              cursor: queued === 0 ? "not-allowed" : "pointer",
            }}
          >
            Cancel pending
          </button>
        </div>
      )}
    </div>
  );
}
