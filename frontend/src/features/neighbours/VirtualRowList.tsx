/**
 * Row virtualisation as a cost control (C2a) — only rendered rows may later
 * be summarised (I9). I5 just wires the virtualizer; demand acquisition is
 * not implemented until I9.
 */
import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { NeighbourRowDto } from "@/api/types";
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
  originFunctionId,
}: {
  rows: NeighbourRowDto[];
  originFunctionId?: number | undefined;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT_PX,
    overscan: 4,
  });

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
      <div style={{ height: String(virtualizer.getTotalSize()), position: "relative" }}>
        {virtualizer.getVirtualItems().map((virtualRow) => {
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
              <NeighbourRow row={row} originFunctionId={originFunctionId} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
