/**
 * Row virtualisation as a cost control — only rendered rows may be
 * summarised. The virtualizer's `overscan: 4` below is the lookahead: demand
 * is acquired for exactly its virtual rows, not every row in a large table.
 */
import { useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { NeighbourRowDto, Priority } from "@/api/types";
import type { FanOutOrigin } from "@/features/canvas/CanvasActions";
import { useSummaryDemand } from "@/hooks/useSummaryDemand";
import type { SurfaceId } from "@/store/demandSlice";
import { NeighbourRow } from "./NeighbourRow";

const ROW_HEIGHT_PX = 32;
const MAX_LIST_HEIGHT_PX = 320;
// Reserved manually rather than relying on `scrollbar-gutter` / `overflow:
// scroll` alone: those only reserve space for *classic* scrollbars. Overlay
// scrollbars (macOS, and — as observed — some Windows/WSLg Chromium/Firefox
// configurations) draw the thumb on top of the content with zero layout
// impact, so the fan-out button (grid's last column) still gets covered
// unless we carve out the space ourselves.
const SCROLLBAR_GUTTER_PX = 14;

export function VirtualRowList({
  rows,
  origin,
  demand,
}: {
  rows: NeighbourRowDto[];
  /** Fan-out provenance for every row in this list (the card + which table).
   * Optional so isolated row rendering (e.g. in a test) still works. */
  origin?: FanOutOrigin | undefined;
  /** Omit demand for isolated rendering; cards pass it to resolve only their
   * visible caller/callee rows. */
  demand?: { surface: SurfaceId; priority: Priority } | undefined;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT_PX,
    overscan: 4,
  });

  const virtualItems = virtualizer.getVirtualItems();
  const visibleFunctionIds = useMemo(
    () =>
      virtualItems
        .map((virtualRow) => rows[virtualRow.index]?.id)
        .filter((id): id is number => id !== undefined),
    [virtualItems, rows],
  );

  const height = Math.min(rows.length * ROW_HEIGHT_PX, MAX_LIST_HEIGHT_PX);
  const canScroll = rows.length * ROW_HEIGHT_PX > MAX_LIST_HEIGHT_PX;

  return (
    <div
      ref={parentRef}
      // `nowheel` is a React Flow convention (https://reactflow.dev/api-reference/types/node-props
      // — see "scrollable content") that stops wheel events from bubbling
      // to the pane. Without it, scrolling the mouse wheel over this list
      // zooms/pans the canvas instead of scrolling the rows.
      className="nowheel"
      style={{
        height,
        // Reserve the scrollbar track permanently (`scroll`, not `auto`) so
        // hovering never causes a scrollbar to pop in and overlap the last
        // column (the fan-out button).
        overflowY: canScroll ? "scroll" : "hidden",
        overflowX: "hidden",
        scrollbarGutter: "stable",
        // Belt-and-braces for overlay-scrollbar platforms/browsers where the
        // above doesn't actually reserve any width (see SCROLLBAR_GUTTER_PX
        // comment) — shrink the row content itself so the button column
        // never sits under the thumb.
        paddingRight: canScroll ? SCROLLBAR_GUTTER_PX : 0,
        boxSizing: "border-box",
      }}
      role="rowgroup"
      aria-label="neighbour-rows"
    >
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {virtualItems.map((virtualRow) => {
          const row = rows[virtualRow.index];
          if (!row) return null;
          return (
            <div
              key={row.id}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: virtualRow.size,
                transform: `translateY(${String(virtualRow.start)}px)`,
              }}
            >
              <NeighbourRow row={row} origin={origin} />
            </div>
          );
        })}
      </div>
      {demand && (
        <RowDemand
          functionIds={visibleFunctionIds}
          surface={demand.surface}
          priority={demand.priority}
        />
      )}
    </div>
  );
}

/** Isolated so the provider-dependent demand hook mounts only when a caller
 * opts in, keeping standalone row rendering usable in tests. */
function RowDemand({
  functionIds,
  surface,
  priority,
}: {
  functionIds: readonly number[];
  surface: SurfaceId;
  priority: Priority;
}) {
  useSummaryDemand({ surface, functionIds, priority, enabled: true });
  return null;
}
