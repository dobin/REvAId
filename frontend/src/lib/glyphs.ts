/**
 * The single source for GraphRev's glyph set (TAD §4.2 / docs/glyphs.md).
 * Both the sidebar legend (D21a) and the row-level UI import from here so the
 * meaning of a glyph is defined exactly once.
 *
 * Note: the PRD's M0-scoping sentence writes `⤲` (U+2932), but every
 * wireframe and the glyph table itself use `⤢` (U+2922) for fan-out. That is
 * a PRD typo; this module uses `⤢`, the form actually used everywhere else.
 */

export const GLYPHS = {
  fanOut: "⤢", // promote to canvas node (D8)
  onCanvas: "◎", // already on canvas — click to pan/focus (D9)
  generating: "◌", // summary generating
  recursive: "↻", // recursive / part of a cycle
  utility: "▫", // utility (high fan-in) — collapsed utility group (D34)
  placeholder: "≡", // outside the ingested module (D35a)
  hasNotes: "📝",
  renamed: "✎",
  error: "!",
  llmMarker: "✨", // marks LLM output (§4.4 three-tier truthfulness)
  menu: "⋯",
  close: "✕",
  collapse: "⌄",
  expand: "▾",
  expandCollapsed: "▸",
  sort: "⇅",
  settings: "⚙",
  color: "🎨",
  search: "🔍",
  resolved: "✓",
  warning: "⚠",
} as const;

/**
 * M0 scoping (verbatim from the PRD): ships fanOut, onCanvas, generating,
 * utility, placeholder, and the error glyph. `recursive`, `hasNotes`, and
 * `renamed` as *row-level* glyphs arrive with D27 (Should) — except
 * `recursive` on the self-recursion row, which D8/§5.1 require in M0.
 * `hasNotes` and `renamed` on the *card header* are M0 (D19, D20).
 */
export const M0_GLYPHS: readonly (keyof typeof GLYPHS)[] = [
  "fanOut",
  "onCanvas",
  "generating",
  "utility",
  "placeholder",
  "error",
];

export type GlyphKey = keyof typeof GLYPHS;

/**
 * Short human-readable labels for each glyph — the single source for both
 * the sidebar `GlyphLegend` and any `title="…"` tooltip a row/card renders
 * (docs/glyphs.md mirrors this wording; keep them in sync).
 */
export const GLYPH_LABELS: Record<GlyphKey, string> = {
  fanOut: "Fan out — promote to canvas node",
  onCanvas: "Already on canvas — click to hide",
  generating: "Summary generating",
  recursive: "Recursive / part of a cycle",
  utility: "Utility (high fan-in)",
  placeholder: "Outside the ingested module",
  hasNotes: "Has analyst notes",
  renamed: "Renamed by analyst",
  error: "Summary error",
  llmMarker: "LLM-generated output",
  menu: "More actions",
  close: "Close",
  collapse: "Collapse",
  expand: "Expand",
  expandCollapsed: "Expand collapsed group",
  sort: "Sort",
  settings: "Settings",
  color: "Color",
  search: "Search",
  resolved: "Resolved",
  warning: "Warning",
};
