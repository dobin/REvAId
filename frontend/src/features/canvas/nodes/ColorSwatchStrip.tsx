/**
 * Minimal inline colour-swatch strip (D16, I6) — a row of palette buttons
 * directly on the card, no dropdown menu (the full `⋯` card menu with a
 * proper colour picker is I10 chrome).
 */
import type { NodeColor } from "@/api/types";

const SWATCH_HEX: Record<NodeColor, string> = {
  slate: "#64748b",
  red: "#ef4444",
  amber: "#f59e0b",
  green: "#22c55e",
  blue: "#3b82f6",
  violet: "#8b5cf6",
  pink: "#ec4899",
};

export function ColorSwatchStrip({
  palette,
  selected,
  onSelect,
}: {
  palette: NodeColor[];
  selected: NodeColor | null;
  onSelect: (color: NodeColor | null) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Node colour"
      style={{ display: "flex", gap: "0.25rem", padding: "0.25rem 0.75rem" }}
    >
      {palette.map((color) => (
        <button
          key={color}
          type="button"
          aria-label={`Set colour ${color}`}
          aria-pressed={selected === color}
          onClick={() => {
            onSelect(selected === color ? null : color);
          }}
          style={{
            width: "0.875rem",
            height: "0.875rem",
            borderRadius: "999px",
            background: SWATCH_HEX[color],
            border: selected === color ? "2px solid #111827" : "1px solid #e5e7eb",
            cursor: "pointer",
            padding: 0,
          }}
        />
      ))}
    </div>
  );
}
