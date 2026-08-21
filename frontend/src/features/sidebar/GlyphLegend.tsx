/**
 * Sidebar glyph legend (D21a) — renders the M0-scoped glyph subset with its
 * label, sourced entirely from `lib/glyphs.ts` so the legend can never drift
 * from what the rest of the UI actually renders.
 */
import { GLYPHS, GLYPH_LABELS, M0_GLYPHS } from "@/lib/glyphs";

export function GlyphLegend() {
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0, fontSize: "0.8125rem" }}>
      {M0_GLYPHS.map((key) => (
        <li
          key={key}
          style={{ display: "flex", gap: "0.5rem", alignItems: "baseline", padding: "0.125rem 0" }}
        >
          <span aria-hidden="true">{GLYPHS[key]}</span>
          <span>{GLYPH_LABELS[key]}</span>
        </li>
      ))}
    </ul>
  );
}
