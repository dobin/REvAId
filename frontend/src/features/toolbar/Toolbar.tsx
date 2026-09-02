/**
 * Toolbar (TAD §2.3) — home link, `ModeIndicator` (ADR 0006) and
 * `QueueChip` (I8). Binary and view selection controls live in the sidebar.
 * Binary selection is on `/`.
 */
import { Link } from "react-router";
import { ModeIndicator } from "./ModeIndicator";
import { QueueChip } from "./QueueChip";

const homeLinkStyle: React.CSSProperties = {
  color: "inherit",
  textDecoration: "none",
};

export function Toolbar() {
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
      <ModeIndicator />
      <div style={{ marginLeft: "auto" }}>
        <QueueChip />
      </div>
    </div>
  );
}
