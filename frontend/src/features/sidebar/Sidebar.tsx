/**
 * Sidebar (TAD §2.3) — I5 hosts only `GlyphLegend`. `OnCanvasList` is
 * deferred to I6 (depends on `view_nodes` persistence).
 */
import { GlyphLegend } from "./GlyphLegend";

export function Sidebar() {
  return (
    <aside style={{ width: "16rem", padding: "1rem", borderRight: "1px solid #e5e7eb" }}>
      <h2 style={{ fontSize: "0.875rem", fontWeight: 600, marginTop: 0 }}>Legend</h2>
      <GlyphLegend />
    </aside>
  );
}
