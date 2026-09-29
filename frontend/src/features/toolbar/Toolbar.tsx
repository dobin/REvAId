/**
 * Toolbar (TAD §2.3) — home link, `ModeIndicator` (ADR 0006) and
 * `QueueChip` (I8). Binary and view selection controls live in the sidebar.
 * Binary selection is on `/`.
 */
import { Link, useLocation } from "react-router";
import { ModeIndicator } from "./ModeIndicator";
import { QueueChip } from "./QueueChip";

const homeLinkStyle: React.CSSProperties = {
  color: "inherit",
  textDecoration: "none",
};

export function Toolbar({ binaryName }: { binaryName?: string }) {
  const location = useLocation();
  const binaryBase = binaryName ? `/${encodeURIComponent(binaryName)}` : null;
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
      {binaryBase && <nav aria-label="Binary pages" style={{ display: "flex", gap: "0.75rem", marginLeft: "0.25rem" }}>
        <Link to={`${binaryBase}/`} aria-current={location.pathname === `${binaryBase}/` ? "page" : undefined} style={{ ...homeLinkStyle, fontSize: "0.875rem", fontWeight: location.pathname === `${binaryBase}/` ? 600 : 400 }}>Explore</Link>
        <Link to={`${binaryBase}/search`} aria-current={location.pathname.endsWith("/search") ? "page" : undefined} style={{ ...homeLinkStyle, fontSize: "0.875rem", fontWeight: location.pathname.endsWith("/search") ? 600 : 400 }}>Search</Link>
      </nav>}
      <ModeIndicator />
      <div style={{ marginLeft: "auto" }}>
        <QueueChip />
      </div>
    </div>
  );
}
