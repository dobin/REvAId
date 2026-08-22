/**
 * One row in a card's caller/callee table (TAD §2.3). FanOut (⤢) promotes
 * the row's function onto the canvas via `useCanvasActions` (D8); when the
 * function is already placed (◎), clicking again hides it (toggles it off).
 * `isSelf` (recursion) keeps the button inert.
 */
import { Glyph } from "@/components/Glyph";
import { toHex } from "@/lib/hex";
import type { NeighbourRowDto } from "@/api/types";
import { useCanvasActions } from "@/features/canvas/CanvasActions";
import { SummaryCell } from "./SummaryCell";

export function NeighbourRow({
  row,
  originFunctionId,
}: {
  row: NeighbourRowDto;
  /** The card this row's table belongs to — the fan-out provenance parent
   * (D8b). Optional so isolated row rendering (e.g. in a test) still works. */
  originFunctionId?: number | undefined;
}) {
  const canvasActions = useCanvasActions();

  const handleClick = () => {
    if (row.isSelf || !canvasActions) return;
    if (row.onCanvas) {
      canvasActions.hideFunction(row.id);
    } else if (originFunctionId !== undefined) {
      canvasActions.fanOutFunction(originFunctionId, row.id);
    }
  };

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
      <button
        type="button"
        disabled={row.isSelf || !canvasActions}
        title={
          row.isSelf
            ? "Recursive call — cannot fan out"
            : row.onCanvas
              ? "Hide — remove from canvas"
              : "Fan out — add to canvas"
        }
        aria-label="fan-out-or-focus"
        onClick={handleClick}
        style={{
          border: "none",
          background: "none",
          padding: "0.125rem 0.25rem",
          cursor: row.isSelf || !canvasActions ? "default" : "pointer",
          borderRadius: "0.25rem",
          transition: "background 0.15s",
          lineHeight: 1,
        }}
        onMouseEnter={(e) => {
          if (!row.isSelf && canvasActions) {
            (e.currentTarget as HTMLButtonElement).style.background = "#f3f4f6";
          }
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "none";
        }}
      >
        <Glyph name={row.onCanvas ? "onCanvas" : "fanOut"} />
      </button>
    </div>
  );
}
