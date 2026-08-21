/**
 * D7/E2a: the caller-suppression notice. "Show anyway" is rendered but
 * disabled — the backend has no bypass parameter for suppression (I5
 * ships no way to actually fetch the suppressed rows).
 */
export function SuppressedNotice({ total }: { total: number }) {
  return (
    <div style={{ padding: "0.5rem 0", fontSize: "0.8125rem", color: "#6b7280" }}>
      Called by {total} —{" "}
      <button type="button" disabled title="Coming soon (I6)">
        Show anyway
      </button>
    </div>
  );
}
