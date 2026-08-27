/**
 * Sidebar "LLM activity" panel — the live view of what the summarization
 * queue is doing right now. Reads the `GET /queue` cache entry, which is
 * kept current by SSE `queue` events: worker-driven events (pop/complete
 * transitions, published with the full per-item lists) update the
 * `inFlight`/`queued` lists instantly, while counter-only events from
 * demand mutations refresh just the counts until the next full event or
 * the 15s fallback refetch.
 *
 * Shows up to a handful of in-flight functions (with elapsed time) and the
 * queued count — enough to answer "is it working, and how far along is
 * it?" without turning the sidebar into a log viewer.
 */
import { useEffect, useState } from "react";
import { Spinner } from "@/components/Spinner";
import { useQueueQuery } from "@/api/queries/queue";

const MAX_IN_FLIGHT_SHOWN = 5;

/**
 * Re-render the caller once per second while `active` is true, so elapsed
 * times tick. Returns a monotonically increasing counter (the value itself
 * is only a dependency anchor — reading `Date.now()` during render is what
 * produces the fresh elapsed labels).
 */
function useTicker(active: boolean): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => {
      setTick((t) => t + 1);
    }, 1000);
    return () => {
      window.clearInterval(id);
    };
  }, [active]);
  return tick;
}

function elapsedLabel(startedAt: string | null): string {
  if (startedAt === null) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - Date.parse(startedAt)) / 1000));
  if (Number.isNaN(seconds)) return "";
  return seconds >= 60 ? `${Math.floor(seconds / 60)}m ${seconds % 60}s` : `${seconds}s`;
}

const itemStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.375rem",
  fontSize: "0.75rem",
  padding: "0.125rem 0",
  color: "#374151",
  minWidth: 0,
};

const nameStyle: React.CSSProperties = {
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
  flex: 1,
};

export function QueuePanel() {
  const { data } = useQueueQuery();
  const inFlight = data?.inFlight ?? [];
  const queued = data?.queued ?? [];
  const total = inFlight.length + queued.length;
  // Tick once per second while anything is in flight, so the elapsed
  // labels count up live instead of freezing at the value computed on the
  // last queue-event render.
  useTicker(total > 0);

  if (total === 0) return null;

  return (
    <div>
      <p style={{ margin: "0 0 0.25rem", fontSize: "0.75rem", color: "#6b7280" }}>
        <Spinner label="Summary generating" /> {inFlight.length} analysing
        {queued.length > 0 ? `, ${queued.length} queued` : ""}
        {data?.pausedUntil && (
          <span style={{ color: "#b45309" }}> — rate-limited, paused</span>
        )}
      </p>
      {inFlight.slice(0, MAX_IN_FLIGHT_SHOWN).map((item) => (
        <div key={item.functionId} style={itemStyle} title={item.displayName}>
          <Spinner label="Summary generating" />
          <span style={nameStyle}>{item.displayName}</span>
          <span style={{ color: "#9ca3af", fontVariantNumeric: "tabular-nums" }}>
            {elapsedLabel(item.startedAt)}
          </span>
        </div>
      ))}
      {inFlight.length > MAX_IN_FLIGHT_SHOWN && (
        <p style={{ margin: 0, fontSize: "0.75rem", color: "#9ca3af" }}>
          +{inFlight.length - MAX_IN_FLIGHT_SHOWN} more…
        </p>
      )}
    </div>
  );
}
