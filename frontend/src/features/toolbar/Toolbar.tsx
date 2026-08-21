/**
 * Toolbar (TAD §2.3) — `BinaryPicker` (I5) + `ViewPicker` (I6). `QueueChip`
 * (I7) is added when the summary queue lands.
 */
import type { BinaryId, ViewId } from "@/api/types";
import { BinaryPicker } from "./BinaryPicker";
import { ViewPicker } from "./ViewPicker";

export function Toolbar({
  selectedBinaryId,
  onSelectBinary,
  selectedViewId,
  onSelectView,
}: {
  selectedBinaryId: BinaryId | null;
  onSelectBinary: (binaryId: BinaryId) => void;
  selectedViewId: ViewId | null;
  onSelectView: (viewId: ViewId) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.75rem",
        padding: "0.5rem 1rem",
        borderBottom: "1px solid #e5e7eb",
      }}
    >
      <strong>GraphRev</strong>
      <BinaryPicker value={selectedBinaryId} onChange={onSelectBinary} />
      {selectedBinaryId !== null && (
        <ViewPicker binaryId={selectedBinaryId} value={selectedViewId} onChange={onSelectView} />
      )}
    </div>
  );
}
