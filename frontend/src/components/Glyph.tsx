/**
 * Thin wrapper around `lib/glyphs.ts` — every glyph rendered in the UI goes
 * through this component so it always carries an accessible label (title +
 * aria-label), never a bare unlabelled character.
 */
import { GLYPHS, GLYPH_LABELS, type GlyphKey } from "@/lib/glyphs";

export function Glyph({ name, className }: { name: GlyphKey; className?: string }) {
  const label = GLYPH_LABELS[name];
  return (
    <span className={className} role="img" aria-label={label} title={label}>
      {GLYPHS[name]}
    </span>
  );
}
