/**
 * Minimal read-only detail panel (I6, pulled forward from I10's full
 * `DetailPanel`). Shows identity/address/kind/signature/fan counts for the
 * currently selected function. Ground-truth code is intentionally shown here
 * rather than on a canvas card, where it would make the graph unreadable.
 */
import { useFunctionQuery } from "@/api/queries/functions";
import { toHex } from "@/lib/hex";
import { useAppStore } from "@/store";

const panelWidth = "42rem";

function CodeSection({ title, code, unavailableMessage }: {
  title: string;
  code: string | null;
  unavailableMessage: string;
}) {
  return (
    <details open style={{ marginTop: "1rem" }}>
      <summary style={{ cursor: "pointer", fontWeight: 600 }}>{title}</summary>
      {code === null ? (
        <p style={{ color: "#6b7280", fontSize: "0.8125rem" }}>{unavailableMessage}</p>
      ) : (
        <pre
          className="gr-ground-truth"
          style={{
            background: "#f8fafc",
            border: "1px solid #e5e7eb",
            borderRadius: "0.375rem",
            fontSize: "0.8125rem",
            lineHeight: 1.5,
            margin: "0.5rem 0 0",
            maxHeight: "20rem",
            overflow: "auto",
            padding: "0.75rem",
            whiteSpace: "pre",
          }}
        >
          <code>{code}</code>
        </pre>
      )}
    </details>
  );
}

export function DetailPanel() {
  const selectedFunctionId = useAppStore((s) => s.selectedFunctionId);
  const clearSelection = useAppStore((s) => s.clearSelection);
  const { data: fn, isPending, isError } = useFunctionQuery(selectedFunctionId);

  if (selectedFunctionId === null) return null;

  return (
    <aside
      style={{
        width: panelWidth,
        minWidth: 0,
        flexShrink: 0,
        overflowY: "auto",
        padding: "1rem",
        borderLeft: "1px solid #e5e7eb",
      }}
      aria-label="Function detail"
    >
      {isPending && <p>Loading…</p>}
      {isError && <p>Could not load function.</p>}
      {fn && (
        <div>
          <div style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem" }}>
            <h2 className="gr-ground-truth" style={{ flex: 1, fontSize: "1rem", marginTop: 0 }}>
              {fn.displayName}
            </h2>
            <button
              type="button"
              aria-label="Close function detail"
              title="Close details"
              onClick={clearSelection}
              style={{
                border: "none",
                background: "none",
                borderRadius: "0.25rem",
                color: "#6b7280",
                cursor: "pointer",
                fontSize: "1.25rem",
                lineHeight: 1,
                padding: "0.25rem",
              }}
            >
              ✕
            </button>
          </div>
          <dl style={{ fontSize: "0.8125rem" }}>
            <dt style={{ color: "#6b7280" }}>Address</dt>
            <dd className="gr-ground-truth">{toHex(fn.address)}</dd>
            <dt style={{ color: "#6b7280" }}>Kind</dt>
            <dd>{fn.kind}</dd>
            {fn.signature && (
              <>
                <dt style={{ color: "#6b7280" }}>Signature</dt>
                <dd className="gr-ground-truth">{fn.signature}</dd>
              </>
            )}
            <dt style={{ color: "#6b7280" }}>Callers / Callees</dt>
            <dd>
              {fn.callerCount} / {fn.calleeCount}
            </dd>
          </dl>
          <CodeSection
            title="Decompiled C"
            code={fn.codeC}
            unavailableMessage="Decompilation unavailable for this function."
          />
          <CodeSection
            title="Assembly"
            code={fn.assembly}
            unavailableMessage="Assembly unavailable for this function."
          />
        </div>
      )}
    </aside>
  );
}
