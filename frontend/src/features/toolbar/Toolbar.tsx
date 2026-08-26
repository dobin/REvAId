/**
 * Toolbar (TAD §2.3) — home link + binary name, `ViewPicker` (I6),
 * `QueueChip` (I8). Binary selection moved to the landing page (`/`).
 */
import { Link } from "react-router";
import type { BinaryId, ViewId } from "@/api/types";
import { QueueChip } from "./QueueChip";
import { ViewPicker } from "./ViewPicker";

const homeLinkStyle: React.CSSProperties = {
  color: "inherit",
  textDecoration: "none",
};

export function Toolbar({
  binaryName,
  binaryId,
  selectedViewId,
  onSelectView,
}: {
  binaryName: string;
  binaryId: BinaryId | null;
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
      <strong>
        <Link to="/" style={homeLinkStyle} title="All binaries">
          GraphRev
        </Link>
      </strong>
      <span
        style={{
          fontFamily: "var(--gr-font-mono, monospace)",
          fontSize: "0.875rem",
          color: "var(--gr-color-ground-truth, #111827)",
        }}
      >
        {binaryName}
      </span>
      {binaryId !== null && (
        <ViewPicker binaryId={binaryId} value={selectedViewId} onChange={onSelectView} />
      )}
      <div style={{ marginLeft: "auto" }}>
        <QueueChip />
      </div>
    </div>
  );
}
