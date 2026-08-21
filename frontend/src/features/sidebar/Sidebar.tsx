/**
 * Sidebar (TAD §2.3) — hosts `PlaceEntryPointButton` (I6 stopgap) and
 * `OnCanvasList` (I6) above the `GlyphLegend`.
 */
import type { BinaryId, ViewId } from "@/api/types";
import { GlyphLegend } from "./GlyphLegend";
import { OnCanvasList } from "./OnCanvasList";
import { PlaceEntryPointButton } from "./PlaceEntryPointButton";

export function Sidebar({
  binaryId,
  viewId,
}: {
  binaryId: BinaryId | null;
  viewId: ViewId | null;
}) {
  return (
    <aside style={{ width: "16rem", padding: "1rem", borderRight: "1px solid #e5e7eb" }}>
      {binaryId !== null && viewId !== null && (
        <PlaceEntryPointButton binaryId={binaryId} viewId={viewId} />
      )}
      <OnCanvasList viewId={viewId} />
      <h2 style={{ fontSize: "0.875rem", fontWeight: 600 }}>Legend</h2>
      <GlyphLegend />
    </aside>
  );
}
