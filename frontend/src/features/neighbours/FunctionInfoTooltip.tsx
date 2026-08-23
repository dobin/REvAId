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
 */
import { useState, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { functionQueryOptions } from "@/api/queries/functions";
import type { FunctionDto, FunctionId } from "@/api/types";

// Small delay so a quick pass over the name doesn't fire a fetch or flash the
// popup — only a deliberate hover surfaces it.
const HOVER_OPEN_DELAY_MS = 200;
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
  const [timer, setTimer] = useState<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = () => {
    if (timer) {
      clearTimeout(timer);
      setTimer(null);
    }
  };

  const handleEnter = () => {
    clearTimer();
    setTimer(
      setTimeout(() => {
        if (anchorRef.current) {
          const rect = anchorRef.current.getBoundingClientRect();
          // Prefer opening below; clamp left so it doesn't run off the right
          // edge of the viewport.
          const left = Math.min(rect.left, window.innerWidth - POPUP_WIDTH_PX - 8);
          setPos({ top: rect.bottom + 4, left });
        }
        setOpen(true);
      }, HOVER_OPEN_DELAY_MS),
    );
  };

  const handleLeave = () => {
    clearTimer();
    setOpen(false);
    setPos(null);
  };

  return (
    <span
      ref={anchorRef}
      style={{ display: "inline-flex", minWidth: 0 }}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      onFocus={handleEnter}
      onBlur={handleLeave}
    >
      {children}
      {open &&
        pos &&
        createPortal(
          <div
            role="tooltip"
            style={{
              position: "fixed",
              top: pos.top,
              left: pos.left,
              zIndex: 9999,
              width: POPUP_WIDTH_PX,
              maxHeight: "18rem",
              overflowY: "auto",
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
              // Prevent the tooltip itself from triggering a mouseLeave on the
              // anchor when the pointer moves onto it.
              pointerEvents: "none",
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

  if (status === "none" || (!short && !long)) {
    return <p style={{ margin: 0, color: "#9ca3af" }}>No summary yet.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {short && (
        <p style={{ margin: 0, fontWeight: 600 }}>
          {short}
          {status === "stale" && " (stale)"}
        </p>
      )}
      {long && <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{long}</p>}
    </div>
  );
}
