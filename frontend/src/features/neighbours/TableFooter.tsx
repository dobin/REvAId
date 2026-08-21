/**
 * "showing N of total · Fan out all" footer. "Fan out all" is disabled — the
 * behavior it triggers (batch node placement) is I6 scope.
 */
export function TableFooter({ shown, total }: { shown: number; total: number }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        fontSize: "0.75rem",
        color: "#6b7280",
        padding: "0.25rem 0",
      }}
    >
      <span>
        showing {shown} of {total}
      </span>
      <button type="button" disabled title="Coming soon (I6)">
        Fan out all
      </button>
    </div>
  );
}
