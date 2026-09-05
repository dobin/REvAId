/**
 * Landing page (`/`) — table of ingested binaries with per-row actions:
 * open (navigates to `/{name}/`), stats (dialog), and delete (typed-name
 * confirm dialog feeding `DELETE /binaries/{id}?confirm=`).
 */
import { useState } from "react";
import { useNavigate } from "react-router";
import { useBinariesQuery } from "@/api/queries/binaries";
import type { BinarySummaryDto } from "@/api/types";
import { EmptyState } from "@/components/EmptyState";
import { Dialog } from "@/components/Dialog";
import { ImportBinaryButton } from "@/features/sidebar/ImportBinaryButton";
import { DeleteBinaryDialog } from "./DeleteBinaryDialog";

const pageStyle: React.CSSProperties = {
  maxWidth: "56rem",
  margin: "0 auto",
  padding: "2.5rem 1.5rem",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: "0.875rem",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "0.5rem 0.75rem",
  borderBottom: "2px solid #e5e7eb",
  fontSize: "0.75rem",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  color: "var(--gr-color-muted, #6b7280)",
};

const tdStyle: React.CSSProperties = {
  padding: "0.5rem 0.75rem",
  borderBottom: "1px solid #f3f4f6",
};

const actionButtonStyle: React.CSSProperties = {
  padding: "0.25rem 0.625rem",
  fontSize: "0.8125rem",
  borderRadius: "0.375rem",
  border: "1px solid #d1d5db",
  background: "#f9fafb",
  cursor: "pointer",
};

const dangerButtonStyle: React.CSSProperties = {
  ...actionButtonStyle,
  color: "#b91c1c",
  borderColor: "#fca5a5",
  background: "#fef2f2",
};

function formatCreatedAt(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

function StatsDialog({
  binary,
  open,
  onOpenChange,
}: {
  binary: BinarySummaryDto;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const rows: [string, string][] = [
    ["Name", binary.name],
    ["Version", binary.version],
    ["Functions", String(binary.functionCount)],
    ["Call edges", String(binary.edgeCount)],
    ["Last view", binary.lastViewId === null ? "—" : `#${String(binary.lastViewId)}`],
    ["Ingested", formatCreatedAt(binary.createdAt)],
  ];
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={`Stats — ${binary.name}`}>
      <table style={{ ...tableStyle, fontSize: "0.8125rem" }}>
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label}>
              <td style={{ ...tdStyle, color: "var(--gr-color-muted, #6b7280)", width: "8rem" }}>
                {label}
              </td>
              <td style={{ ...tdStyle, fontFamily: "var(--gr-font-mono, monospace)" }}>
                {value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Dialog>
  );
}

export function BinariesPage() {
  const navigate = useNavigate();
  const { data: binaries, isPending, isError } = useBinariesQuery();
  const [statsBinary, setStatsBinary] = useState<BinarySummaryDto | null>(null);
  const [deleteBinary, setDeleteBinary] = useState<BinarySummaryDto | null>(null);

  return (
    <div style={pageStyle}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: "1.5rem",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "1.25rem" }}>Binaries</h1>
        <ImportBinaryButton
          onImported={() => {
            // The list refreshes via query invalidation; stay on the page.
          }}
        />
      </div>

      {isPending && <EmptyState title="Loading binaries…" />}
      {isError && <EmptyState title="Could not load binaries." />}
      {binaries !== undefined && binaries.length === 0 && (
        <EmptyState
          title="No binaries ingested yet."
          description="Import a Ghidra JSON export to get started."
        />
      )}

      {binaries !== undefined && binaries.length > 0 && (
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>Name</th>
              <th style={thStyle}>Version</th>
              <th style={thStyle}>Functions</th>
              <th style={thStyle}>Edges</th>
              <th style={thStyle}>Ingested</th>
              <th style={thStyle}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {binaries.map((binary) => (
              <tr key={binary.id}>
                <td
                  style={{
                    ...tdStyle,
                    fontFamily: "var(--gr-font-mono, monospace)",
                    color: "var(--gr-color-ground-truth, #111827)",
                  }}
                >
                  {binary.name}
                </td>
                <td style={tdStyle}>{binary.version}</td>
                <td style={tdStyle}>{binary.functionCount}</td>
                <td style={tdStyle}>{binary.edgeCount}</td>
                <td style={tdStyle}>{formatCreatedAt(binary.createdAt)}</td>
                <td style={tdStyle}>
                  <div style={{ display: "flex", gap: "0.375rem" }}>
                    <button
                      type="button"
                      style={actionButtonStyle}
                      onClick={() => { void navigate(`/${encodeURIComponent(binary.name)}/`); }}
                    >
                      Open
                    </button>
                    <button
                      type="button"
                      style={actionButtonStyle}
                      onClick={() => { setStatsBinary(binary); }}
                    >
                      Stats
                    </button>
                    <button
                      type="button"
                      style={dangerButtonStyle}
                      onClick={() => { setDeleteBinary(binary); }}
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {statsBinary !== null && (
        <StatsDialog binary={statsBinary} open onOpenChange={() => { setStatsBinary(null); }} />
      )}
      {deleteBinary !== null && (
        <DeleteBinaryDialog
          binary={deleteBinary}
          open
          onOpenChange={() => { setDeleteBinary(null); }}
        />
      )}
    </div>
  );
}
