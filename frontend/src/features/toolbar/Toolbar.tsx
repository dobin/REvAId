/**
 * Toolbar (TAD §2.3) — I5 hosts only `BinaryPicker`. `ViewPicker` (I6) and
 * `QueueChip` (I7) are added when their backing features land.
 */
import type { BinaryId } from "@/api/types";
import { BinaryPicker } from "./BinaryPicker";

export function Toolbar({
  selectedBinaryId,
  onSelectBinary,
}: {
  selectedBinaryId: BinaryId | null;
  onSelectBinary: (binaryId: BinaryId) => void;
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
    </div>
  );
}
