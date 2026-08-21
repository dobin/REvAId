/**
 * Sidebar (TAD §2.3) — hosts `OnCanvasList` (I6) above the `GlyphLegend`.
 */
import type { ViewId } from "@/api/types";
import { GlyphLegend } from "./GlyphLegend";
import { OnCanvasList } from "./OnCanvasList";

export function Sidebar({ viewId }: { viewId: ViewId | null }) {
  return (
    <aside style={{ width: "16rem", padding: "1rem", borderRight: "1px solid #e5e7eb" }}>
      <OnCanvasList viewId={viewId} />
      <h2 style={{ fontSize: "0.875rem", fontWeight: 600 }}>Legend</h2>
      <GlyphLegend />
    </aside>
  );
}
