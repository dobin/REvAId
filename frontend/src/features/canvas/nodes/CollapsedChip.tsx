/**
 * Collapsed card representation (D14) — a small chip instead of the full
 * card body. Clicking expands it back (patches `collapsed:false`).
 */
import { Glyph } from "@/components/Glyph";
import { toHex } from "@/lib/hex";
import type { FunctionDto } from "@/api/types";

export function CollapsedChip({ fn, onExpand }: { fn: FunctionDto; onExpand: () => void }) {
  return (
    <button
      type="button"
      onClick={onExpand}
      aria-label={`Expand ${fn.displayName}`}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.375rem",
        padding: "0.375rem 0.625rem",
        background: "white",
        border: "1px solid #d1d5db",
        borderRadius: "999px",
        cursor: "pointer",
        fontSize: "0.75rem",
      }}
    >
      <Glyph name="expandCollapsed" />
      <span className="gr-ground-truth">{fn.displayName}</span>
      <span className="gr-ground-truth" style={{ color: "#6b7280" }}>
        {toHex(fn.address)}
      </span>
    </button>
  );
}
