/**
 * Sidebar function search (D9/I11 stopgap) — a single text field that
 * searches `name_ghidra`, `name_analyst`, and `address` (via
 * `GET /binaries/{id}/functions?q=`, B11/E1a) and lets the user place any
 * matching function onto the canvas, closing the long-standing gap where
 * `PlaceEntryPointButton` only ever offered the binary's #1 entry point.
 *
 * A single hit is still shown in the results box (not auto-selected) so the
 * user can see what they are about to add before committing.
 */
import { useState } from "react";
import { useFunctionSearchQuery } from "@/api/queries/binaries";
import { usePatchViewNodesMutation } from "@/api/queries/viewNodes";
import type { BinaryId, FunctionSearchRowDto, ViewId } from "@/api/types";
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

export function FunctionSearchInput({
  binaryId,
  viewId,
}: {
  binaryId: BinaryId | null;
  viewId: ViewId | null;
}) {
  const [text, setText] = useState("");
  const debounced = useDebouncedValue(text, DEBOUNCE_MS);
  const search = useFunctionSearchQuery(binaryId, debounced);
  const patchNodes = usePatchViewNodesMutation(viewId ?? 0);
  const canvasActions = useCanvasActionsFromRegistry();

  const rows = search.data?.rows ?? [];
  const showResults = debounced.trim().length > 0 && binaryId !== null;

  const placeFunction = (row: FunctionSearchRowDto) => {
    if (viewId === null) return;
    patchNodes.mutate(
      { upsert: [{ functionId: row.id, visible: true, originKind: "root" }] },
      {
        onSuccess: () => {
          canvasActions?.focusFunction(row.id);
        },
      },
    );
    setText("");
  };

  return (
    <div>
      <input
        type="text"
        aria-label="Search functions"
        placeholder="Search function to add to canvas"
        value={text}
        disabled={binaryId === null || viewId === null}
        onChange={(e) => {
          setText(e.target.value);
        }}
        style={inputStyle}
      />
      {showResults && (
        <div style={resultsBoxStyle} role="listbox" aria-label="Function search results">
          {search.isPending ? (
            <p style={{ fontSize: "0.75rem", color: "#6b7280", padding: "0.25rem 0.5rem", margin: 0 }}>
              Searching…
            </p>
          ) : rows.length === 0 ? (
            <p style={{ fontSize: "0.75rem", color: "#6b7280", padding: "0.25rem 0.5rem", margin: 0 }}>
              No matches.
            </p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {rows.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={false}
                    disabled={patchNodes.isPending}
                    onClick={() => {
                      placeFunction(row);
                    }}
                    style={rowButtonStyle}
                    title={`Add ${row.displayName} to the canvas`}
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
