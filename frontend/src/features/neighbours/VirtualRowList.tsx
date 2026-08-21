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

  return (
    <div
      ref={parentRef}
      style={{ height, overflow: "auto" }}
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
