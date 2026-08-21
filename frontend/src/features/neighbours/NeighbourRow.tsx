/**
 * One row in a card's caller/callee table (TAD §2.3). FanOut (⤢) / Focus
 * (◎) buttons are rendered but inert in I5 — the behavior they trigger
 * (view_nodes persistence) is I6 scope.
 */
import { Glyph } from "@/components/Glyph";
import { toHex } from "@/lib/hex";
import type { NeighbourRowDto } from "@/api/types";
import { SummaryCell } from "./SummaryCell";

export function NeighbourRow({ row }: { row: NeighbourRowDto }) {
  return (
    <div
      role="row"
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto auto",
        gap: "0.5rem",
        alignItems: "center",
        padding: "0.25rem 0",
        borderBottom: "1px solid #f3f4f6",
      }}
    >
      <span className="gr-ground-truth" style={{ fontSize: "0.75rem", color: "#6b7280" }}>
        {toHex(row.address)}
      </span>
      <span style={{ display: "flex", alignItems: "center", gap: "0.375rem", minWidth: 0 }}>
        {row.kind === "placeholder" && <Glyph name="placeholder" />}
        {row.isSelf && <Glyph name="recursive" />}
        {row.isUtility && <Glyph name="utility" />}
        {row.hasNotes && <Glyph name="hasNotes" />}
        {row.isRenamed && <Glyph name="renamed" />}
        <span
          className="gr-ground-truth"
          style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
        >
          {row.displayName}
        </span>
      </span>
      <SummaryCell
        status={row.summaryStatus}
        summaryShort={row.summaryShort}
        lowConfidence={row.summaryLowConfidence}
      />
      <button type="button" disabled title="Coming soon (I6)" aria-label="fan-out-or-focus">
        <Glyph name={row.onCanvas ? "onCanvas" : "fanOut"} />
      </button>
    </div>
  );
}
