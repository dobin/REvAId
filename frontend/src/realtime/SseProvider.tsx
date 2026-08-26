/**
 * `EventSource` lifecycle for `GET /events` (TAD §2.7/§4.3, E5). Mounted
 * once near the root (`App.tsx`) — this component renders nothing; its only
 * job is keeping the Query cache authoritative via `applyServerEvent`.
 *
 * Native `EventSource` gives automatic reconnect-with-backoff for free
 * (TAD §1.3's own rationale for choosing it over a hand-rolled WebSocket
 * client). This component's added value is exactly the two things
 * `EventSource` does NOT do on its own:
 *   1. Decode each named SSE event's JSON `data:` payload into a typed
 *      `ServerEvent` and dispatch it to `applyServerEvent`.
 *   2. On reconnect after a drop (`EventSource`'s own `error` → next `open`
 *      transition), run `reconcileAfterReconnect` — "never trust client
 *      memory across a gap" (TAD §2.7).
 */
import { useEffect, useRef, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { BinaryEvent, QueueEvent, ReconcileEvent, ServerEvent, SummaryEvent } from "@/api/types";
import { applyServerEvent, reconcileAfterReconnect } from "./applyEvents";

const EVENTS_URL = "/api/v1/events";

function parseSummaryEvent(raw: unknown): SummaryEvent | null {
  if (typeof raw !== "object" || raw === null) return null;
  const data = raw as Record<string, unknown>;
  if (typeof data.functionId !== "number" || typeof data.summaryStatus !== "string") return null;
  return {
    type: "summary",
    functionId: data.functionId,
    summaryStatus: data.summaryStatus as SummaryEvent["summaryStatus"],
    summaryShort: typeof data.summaryShort === "string" ? data.summaryShort : null,
    summaryModel: typeof data.summaryModel === "string" ? data.summaryModel : null,
    lowConfidence: data.lowConfidence === true,
    generatedAt: typeof data.generatedAt === "string" ? data.generatedAt : null,
    errorCode: typeof data.errorCode === "string" ? data.errorCode : null,
    nameLlm: typeof data.nameLlm === "string" ? data.nameLlm : null,
  };
}

function parseQueueEvent(raw: unknown): QueueEvent | null {
  if (typeof raw !== "object" || raw === null) return null;
  const data = raw as Record<string, unknown>;
  if (typeof data.inFlightCount !== "number" || typeof data.queuedCount !== "number") return null;
  return {
    type: "queue",
    inFlightCount: data.inFlightCount,
    queuedCount: data.queuedCount,
    pausedUntil: typeof data.pausedUntil === "string" ? data.pausedUntil : null,
  };
}

function parseBinaryEvent(raw: unknown): BinaryEvent | null {
  if (typeof raw !== "object" || raw === null) return null;
  const data = raw as Record<string, unknown>;
  if (typeof data.binaryId !== "number") return null;
  return {
    type: "binary",
    binaryId: data.binaryId,
    kind: data.kind === "deleted" ? "deleted" : "imported",
  };
}

function parseReconcileEvent(): ReconcileEvent {
  return { type: "reconcile" };
}

function decodeEvent(eventName: string, raw: string): ServerEvent | null {
  let data: unknown = null;
  if (raw.length > 0) {
    try {
      data = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  switch (eventName) {
    case "summary":
      return parseSummaryEvent(data);
    case "queue":
      return parseQueueEvent(data);
    case "binary":
      return parseBinaryEvent(data);
    case "reconcile":
      return parseReconcileEvent();
    default:
      return null;
  }
}

export function SseProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  // Tracks whether we've ever been connected, so the FIRST `open` doesn't
  // trigger a needless reconcile — only a re-open *after* an `error` should
  // (TAD §2.7: "on `EventSource` `open` after an error").
  const hadErrorRef = useRef(false);

  useEffect(() => {
    const source = new EventSource(EVENTS_URL);

    const handleOpen = () => {
      if (hadErrorRef.current) {
        reconcileAfterReconnect(queryClient);
        hadErrorRef.current = false;
      }
    };
    const handleError = () => {
      hadErrorRef.current = true;
    };
    const makeHandler = (eventName: string) => (evt: MessageEvent<string>) => {
      const event = decodeEvent(eventName, evt.data);
      if (event) applyServerEvent(queryClient, event);
    };

    const handleSummary = makeHandler("summary");
    const handleQueue = makeHandler("queue");
    const handleBinary = makeHandler("binary");
    const handleReconcile = makeHandler("reconcile");

    source.addEventListener("open", handleOpen);
    source.addEventListener("error", handleError);
    source.addEventListener("summary", handleSummary);
    source.addEventListener("queue", handleQueue);
    source.addEventListener("binary", handleBinary);
    source.addEventListener("reconcile", handleReconcile);

    return () => {
      source.removeEventListener("open", handleOpen);
      source.removeEventListener("error", handleError);
      source.removeEventListener("summary", handleSummary);
      source.removeEventListener("queue", handleQueue);
      source.removeEventListener("binary", handleBinary);
      source.removeEventListener("reconcile", handleReconcile);
      source.close();
    };
  }, [queryClient]);

  return children;
}
