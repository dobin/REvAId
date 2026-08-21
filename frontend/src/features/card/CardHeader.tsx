/**
 * Card header (D19, D20) — read-only in I5: no inline rename (I10). Shows
 * display name, hex address, kind, and the renamed/has-notes glyphs.
 */
import { Glyph } from "@/components/Glyph";
import { toHex } from "@/lib/hex";
import type { FunctionDto } from "@/api/types";

export function CardHeader({ fn }: { fn: FunctionDto }) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.5rem",
        padding: "0.5rem 0.75rem",
        borderBottom: "1px solid #e5e7eb",
        fontWeight: 600,
      }}
    >
      {fn.isRenamed && <Glyph name="renamed" />}
      <span className="gr-ground-truth" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
        {fn.displayName}
      </span>
      <span className="gr-ground-truth" style={{ fontSize: "0.75rem", color: "#6b7280" }}>
        {toHex(fn.address)}
      </span>
      <span style={{ fontSize: "0.6875rem", color: "#6b7280" }}>{fn.kind}</span>
      {fn.hasNotes && <Glyph name="hasNotes" />}
    </header>
  );
}
