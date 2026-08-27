/**
 * `OnCanvasSearch` — replaces the old `OnCanvasList` (I6). Instead of
 * listing every visible node, the user types a function name and we filter
 * the binary-wide function search (B11/E1a) down to functions that are
 * already on this view's canvas; picking a result focuses the node, exactly
 * like clicking the old list row did.
 */
import { useMemo, useState } from "react";
import { useViewQuery } from "@/api/queries/views";
import { useFunctionSearchQuery } from "@/api/queries/binaries";
import type { BinaryId, ViewId } from "@/api/types";
import { useCanvasActionsFromRegistry } from "@/features/canvas/CanvasActions";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const DEBOUNCE_MS = 250;

const inputStyle: React.CSSProperties = {
  width: "100%",
  fontSize: "0.8125rem",
  padding: "0.25rem 0.5rem",
  borderRadius: "0.375rem",
  border: "1px solid #d1d5db",
  boxSizing: "border-box",
};

const resultsBoxStyle: React.CSSProperties = {
  marginTop: "0.375rem",
  maxHeight: "12rem",
  overflowY: "auto",
  border: "1px solid #e5e7eb",
  borderRadius: "0.375rem",
};

const rowButtonStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "stretch",
  width: "100%",
  textAlign: "left",
  background: "none",
  border: "none",
  borderBottom: "1px solid #f3f4f6",
  cursor: "pointer",
  padding: "0.25rem 0.5rem",
  fontSize: "0.75rem",
};

export function OnCanvasSearch({
  binaryId,
  viewId,
}: {
  binaryId: BinaryId | null;
  viewId: ViewId | null;
}) {
  const [text, setText] = useState("");
  const debounced = useDebouncedValue(text, DEBOUNCE_MS);
  const view = useViewQuery(viewId);
  const search = useFunctionSearchQuery(binaryId, debounced);
  const canvasActions = useCanvasActionsFromRegistry();

  const onCanvasIds = useMemo(() => {
    const ids = new Set<number>();
    for (const node of view.data?.nodes ?? []) {
      if (node.visible) ids.add(node.functionId);
    }
    return ids;
  }, [view.data]);

  const rows = (search.data?.rows ?? []).filter((row) => onCanvasIds.has(row.id));
  const showResults =
    debounced.trim().length > 0 && binaryId !== null && viewId !== null;

  const jumpTo = (functionId: number) => {
    canvasActions?.focusFunction(functionId);
    setText("");
  };

  return (
    <div>
      <input
        type="text"
        aria-label="Search functions on canvas"
        placeholder="Jump to function on canvas"
        value={text}
        disabled={binaryId === null || viewId === null}
        onChange={(e) => {
          setText(e.target.value);
        }}
        style={inputStyle}
      />
      {showResults && (
        <div style={resultsBoxStyle} role="listbox" aria-label="On-canvas search results">
          {search.isPending ? (
            <p style={{ fontSize: "0.75rem", color: "#6b7280", padding: "0.25rem 0.5rem", margin: 0 }}>
              Searching…
            </p>
          ) : rows.length === 0 ? (
            <p style={{ fontSize: "0.75rem", color: "#6b7280", padding: "0.25rem 0.5rem", margin: 0 }}>
              No functions on canvas match.
            </p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {rows.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={false}
                    onClick={() => {
                      jumpTo(row.id);
                    }}
                    style={rowButtonStyle}
                    title={`Jump to ${row.displayName}`}
                  >
                    <span className="gr-ground-truth">{row.displayName}</span>
                    <span style={{ color: "#6b7280" }}>
                      0x{row.address.toString(16)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
