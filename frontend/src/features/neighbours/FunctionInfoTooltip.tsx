/**
 * Hover popup over a neighbour row's function name (§4.3 card affordances).
 * Shows the function's short + long summary on hover. The full record —
 * including `summary.long`, which the narrow `NeighbourRowDto` deliberately
 * omits (only `summaryShort` rides along in the table page) — is fetched
 * lazily via the *shared* `functionQueryOptions` so it provably reuses the
 * same react-query cache entry the detail panel / fan-out prefetch already
 * warms; hover never triggers a redundant request.
 *
 * The popup is rendered into a **portal** (document.body) so it escapes the
 * VirtualRowList's `overflow: scroll` container and React Flow's own
 * `overflow: hidden` wrapper — both of which would clip a normally-positioned
 * child.  Absolute screen coords from `getBoundingClientRect` + `position:
 * fixed` achieve this without any z-index arms-race against the canvas.
 *
 * Side-effect free (C2c): a GET only, no summary-demand wiring here.
 *
 * The popup is **interactable**: the pointer can move off the anchor onto the
 * popup itself to scroll a long summary or select its text, without it
 * vanishing. A short close DELAY on leave (cancelled if the pointer re-enters
 * either the anchor or the popup) bridges the pointer's trip across the small
 * gap between them; the popup carries its own mouse-enter/leave handlers.
 * `Escape` also closes it.
 */
import { useState, useRef, useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { functionQueryOptions } from "@/api/queries/functions";
import { SummaryBody } from "@/components/SummaryBody";
import type { FunctionDto, FunctionId } from "@/api/types";

// Small delay so a quick pass over the name doesn't fire a fetch or flash the
// popup — only a deliberate hover surfaces it.
const HOVER_OPEN_DELAY_MS = 400;
// Grace period after the pointer leaves the anchor so it can travel onto the
// popup (to scroll / select) before we close. Cancelled on re-enter.
const HOVER_CLOSE_DELAY_MS = 120;
const POPUP_WIDTH_PX = 416; // 26rem @ 16px base

export function FunctionInfoTooltip({
  functionId,
  children,
}: {
  functionId: FunctionId;
  children: ReactNode;
}) {
  const anchorRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const openTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearOpenTimer = () => {
    if (openTimerRef.current) {
      clearTimeout(openTimerRef.current);
      openTimerRef.current = null;
    }
  };
  const clearCloseTimer = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  // Clean up any pending timers if the row unmounts (e.g. virtualised out)
  // while a hover is in flight.
  useEffect(() => {
    return () => {
      clearOpenTimer();
      clearCloseTimer();
    };
  }, []);

  const openNow = () => {
    if (anchorRef.current) {
      const rect = anchorRef.current.getBoundingClientRect();
      // Prefer opening below; clamp left so it doesn't run off the right edge
      // of the viewport. No vertical gap — the popup abuts the anchor so the
      // pointer can travel onto it without crossing a dead zone that would
      // otherwise fire a mouseLeave and close it.
      const left = Math.min(rect.left, window.innerWidth - POPUP_WIDTH_PX - 8);
      setPos({ top: rect.bottom, left });
    }
    setOpen(true);
  };

  // Pointer entered the anchor (or the popup): cancel a pending close, and if
  // not already open, schedule the open after the deliberate-hover delay.
  const handleEnter = () => {
    clearCloseTimer();
    if (open) return;
    clearOpenTimer();
    openTimerRef.current = setTimeout(openNow, HOVER_OPEN_DELAY_MS);
  };

  // Pointer left the anchor (or the popup): cancel a pending open, and
  // schedule a delayed close so the pointer has time to reach the other
  // element. A re-enter of either cancels this before it fires.
  const scheduleClose = () => {
    clearOpenTimer();
    clearCloseTimer();
    closeTimerRef.current = setTimeout(() => {
      setOpen(false);
      setPos(null);
    }, HOVER_CLOSE_DELAY_MS);
  };

  // Focus/blur (keyboard) close immediately — there's no pointer to bridge.
  const handleBlur = () => {
    clearOpenTimer();
    clearCloseTimer();
    setOpen(false);
    setPos(null);
  };

  // Escape closes an open popup. Self-contained so it needn't depend on the
  // per-render `handleBlur` closure (which would re-bind the listener every
  // render); it only ever runs while `open` is true.
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      clearOpenTimer();
      clearCloseTimer();
      setOpen(false);
      setPos(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <span
      ref={anchorRef}
      style={{ display: "inline-flex", minWidth: 0 }}
      onMouseEnter={handleEnter}
      onMouseLeave={scheduleClose}
      onFocus={handleEnter}
      onBlur={handleBlur}
    >
      {children}
      {open &&
        pos &&
        createPortal(
          <div
            role="tooltip"
            onMouseEnter={handleEnter}
            onMouseLeave={scheduleClose}
            style={{
              position: "fixed",
              top: pos.top,
              left: pos.left,
              zIndex: 9999,
              width: POPUP_WIDTH_PX,
              maxHeight: "18rem",
              overflowY: "auto",
              // Slight negative top margin overlaps the anchor's bottom edge so
              // there's no 1px gap for the pointer to fall through en route.
              marginTop: "-2px",
              padding: "0.75rem",
              background: "#ffffff",
              border: "1px solid #d1d5db",
              borderRadius: "0.375rem",
              boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
              fontSize: "0.8125rem",
              lineHeight: 1.5,
              color: "#374151",
              whiteSpace: "normal",
              textAlign: "left",
              cursor: "default",
            }}
          >
            {/* Only mount the fetching child once the popup opens, so a plain
                `NeighbourRow` (no `QueryClientProvider` in scope) never
                touches react-query until the user actually hovers. */}
            <TooltipContent functionId={functionId} />
          </div>,
          document.body,
        )}
    </span>
  );
}

function TooltipContent({ functionId }: { functionId: FunctionId }) {
  const { data, isPending, isError } = useQuery(functionQueryOptions(functionId));

  if (isPending) return <p style={{ margin: 0, color: "#6b7280" }}>Loading summary…</p>;
  if (isError) return <p style={{ margin: 0, color: "#b91c1c" }}>Could not load summary.</p>;
  return <TooltipBody fn={data} />;
}

function TooltipBody({ fn }: { fn: FunctionDto }) {
  const { status, short, long } = fn.summary;
  return <SummaryBody status={status} short={short} long={long} />;
}
