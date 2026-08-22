/**
 * One row in a card's caller/callee table (TAD §2.3). FanOut (⤢) promotes
 * the row's function onto the canvas via `useCanvasActions` (D8); when the
 * function is already placed (◎), clicking again hides it (toggles it off).
 * `isSelf` (recursion) keeps the button inert.
 */
import { Glyph } from "@/components/Glyph";
import { toHex } from "@/lib/hex";
import type { NeighbourRowDto } from "@/api/types";
import { useCanvasActions, type FanOutOrigin } from "@/features/canvas/CanvasActions";

export function NeighbourRow({
  row,
  origin,
}: {
  row: NeighbourRowDto;
  /** Fan-out provenance for this row — the card its table belongs to and
   * which table (callees -> right, callers -> left) (D8b). Optional so
   * isolated row rendering (e.g. in a test) still works; a row with no
   * origin renders an inert fan-out button. */
  origin?: FanOutOrigin | undefined;
}) {
  const canvasActions = useCanvasActions();

  const handleClick = () => {
    if (row.isSelf || !canvasActions) return;
    if (row.onCanvas) {
      canvasActions.hideFunction(row.id);
    } else if (origin !== undefined) {
      canvasActions.fanOutFunction(origin, row.id);
    }
  };

  // The fan-out control does nothing for a self-row (recursion), outside a
  // CanvasView (no actions), or — for a not-yet-placed row — with no origin
  // to attribute the new node to. An on-canvas row only ever hides, so it
  // stays live even without an origin. Disable rather than silently no-op:
  // an enabled-but-inert button was the original caller fan-out bug.
  const disabled = row.isSelf || !canvasActions || (!row.onCanvas && origin === undefined);

  return (
    <div
      role="row"
      style={{
        display: "grid",
        gridTemplateColumns: "4.5rem 1fr auto",
        gap: "0.5rem",
        alignItems: "center",
        padding: "0.25rem 0",
        borderBottom: "1px solid #f3f4f6",
      }}
    >
      <span
        className="gr-ground-truth"
        style={{
          fontSize: "0.75rem",
          color: "#6b7280",
          textAlign: "right",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {toHex(row.address)}
      </span>
      <span style={{ display: "flex", alignItems: "center", gap: "0.375rem", minWidth: 0 }}>
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
      <button
        type="button"
        disabled={disabled}
        title={
          row.isSelf
            ? "Recursive call — cannot fan out"
            : row.onCanvas
              ? "Hide — remove from canvas"
              : origin?.direction === "callers"
                ? "Fan out caller — add to canvas (left)"
                : "Fan out — add to canvas"
        }
        aria-label="fan-out-or-focus"
        onClick={handleClick}
        style={{
          border: "none",
          background: "none",
          padding: "0.125rem 0.25rem",
          cursor: disabled ? "default" : "pointer",
          borderRadius: "0.25rem",
          transition: "background 0.15s",
          lineHeight: 1,
        }}
        onMouseEnter={(e) => {
          if (!disabled) {
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
