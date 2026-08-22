/**
 * Card header (D19, D20) — read-only in I5: no inline rename (I10). Shows
 * display name, hex address, kind, and the renamed/has-notes glyphs.
 * The colour swatch (D16) lives here: a small square that opens an inline
 * palette when clicked.
 */
import { useState } from "react";
import { Glyph } from "@/components/Glyph";
import { toHex } from "@/lib/hex";
import type { FunctionDto, NodeColor } from "@/api/types";
import { SWATCH_HEX } from "@/features/canvas/nodes/ColorSwatchStrip";

export function CardHeader({
  fn,
  color = null,
  palette,
  onColorSelect,
}: {
  fn: FunctionDto;
  color?: NodeColor | null;
  palette?: NodeColor[];
  onColorSelect?: (color: NodeColor | null) => void;
}) {
  const [paletteOpen, setPaletteOpen] = useState(false);

  const swatchColor = color ? SWATCH_HEX[color] : "#e5e7eb";
  const canColor = palette && onColorSelect;

  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.5rem",
        padding: "0.5rem 0.75rem",
        borderBottom: paletteOpen ? "none" : "1px solid #e5e7eb",
        fontWeight: 600,
        position: "relative",
      }}
    >
      {canColor && (
        <button
          type="button"
          aria-label={`Change colour${color ? `: ${color}` : ""}`}
          title={color ?? "No colour"}
          onClick={(e) => {
            e.stopPropagation();
            setPaletteOpen((o) => !o);
          }}
          style={{
            width: "0.875rem",
            height: "0.875rem",
            flexShrink: 0,
            borderRadius: "2px",
            background: swatchColor,
            border: "1px solid #9ca3af",
            cursor: "pointer",
            padding: 0,
          }}
        />
      )}
      {fn.isRenamed && <Glyph name="renamed" />}
      <span className="gr-ground-truth" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
        {fn.displayName}
      </span>
      <span className="gr-ground-truth" style={{ fontSize: "0.75rem", color: "#6b7280" }}>
        {toHex(fn.address)}
      </span>
      {fn.hasNotes && <Glyph name="hasNotes" />}
      {canColor && paletteOpen && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            zIndex: 10,
            display: "flex",
            flexWrap: "wrap",
            gap: "0.25rem",
            padding: "0.375rem 0.75rem",
            background: "white",
            borderBottom: "1px solid #e5e7eb",
            borderTop: "1px solid #e5e7eb",
          }}
        >
          {/* "no colour" option */}
          <button
            type="button"
            aria-label="Remove colour"
            title="No colour"
            aria-pressed={color === null}
            onClick={() => {
              onColorSelect(null);
              setPaletteOpen(false);
            }}
            style={{
              width: "1rem",
              height: "1rem",
              borderRadius: "2px",
              background: "white",
              border: color === null ? "2px solid #111827" : "1px solid #9ca3af",
              cursor: "pointer",
              padding: 0,
              fontSize: "0.6rem",
            }}
          >
            ✕
          </button>
          {palette.map((c) => (
            <button
              key={c}
              type="button"
              aria-label={`Set colour ${c}`}
              aria-pressed={color === c}
              onClick={() => {
                onColorSelect(c);
                setPaletteOpen(false);
              }}
              style={{
                width: "1rem",
                height: "1rem",
                borderRadius: "2px",
                background: SWATCH_HEX[c],
                border: color === c ? "2px solid #111827" : "1px solid #e5e7eb",
                cursor: "pointer",
                padding: 0,
              }}
            />
          ))}
        </div>
      )}
    </header>
  );
}
