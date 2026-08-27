/**
 * Sidebar function search (D9/I11 stopgap) — a single text field that
 * searches `name_ghidra`, `name_analyst`, and `address` (via
 * `GET /binaries/{id}/functions?q=`, B11/E1a). Picking a match focuses it
 * when it is already visible on the canvas; otherwise it places the function,
 * closing the gap where `PlaceEntryPointButton` only offered the binary's #1
 * entry point.
 *
 * A single hit is still shown in the results box (not auto-selected) so the
 * user can see whether selecting it will jump to or add the function.
 */
import { useMemo, useState } from "react";
import { useFunctionAddressQuery, useFunctionSearchQuery } from "@/api/queries/binaries";
import { usePatchViewNodesMutation } from "@/api/queries/viewNodes";
import { useViewQuery } from "@/api/queries/views";
import type { BinaryId, ViewId, ViewNodeUpsertRequest } from "@/api/types";
import { useCanvasActionsFromRegistry } from "@/features/canvas/CanvasActions";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { resolveAddressLookup } from "@/lib/address";
import { toHex } from "@/lib/hex";
import { useConnectNewNode } from "./useConnectNewNode";

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
  analysisImageBase,
  runtimeBase,
}: {
  binaryId: BinaryId | null;
  viewId: ViewId | null;
  analysisImageBase: number | null;
  runtimeBase: number | null;
}) {
  const [text, setText] = useState("");
  const debounced = useDebouncedValue(text, DEBOUNCE_MS);
  const lookup = resolveAddressLookup(debounced, runtimeBase, analysisImageBase);
  const view = useViewQuery(viewId);
  const search = useFunctionSearchQuery(binaryId, lookup.kind === "text" ? debounced : "");
  const address = useFunctionAddressQuery(
    binaryId,
    lookup.kind === "address" ? lookup.canonicalAddress : null,
  );
  const patchNodes = usePatchViewNodesMutation(viewId ?? 0);
  const canvasActions = useCanvasActionsFromRegistry();
  const connectNewNode = useConnectNewNode(viewId);

  const rows = search.data?.rows ?? [];
  const resolvedFunction = address.data;
  const showResults = debounced.trim().length > 0 && binaryId !== null;
  const onCanvasIds = useMemo(() => {
    const ids = new Set<number>();
    for (const node of view.data?.nodes ?? []) {
      if (node.visible) ids.add(node.functionId);
    }
    return ids;
  }, [view.data]);

  const selectFunction = (functionId: number) => {
    if (viewId === null) return;
    setText("");

    if (onCanvasIds.has(functionId)) {
      canvasActions?.focusFunction(functionId);
      return;
    }

    // Auto-link to an already-on-canvas caller/callee (mirrors fan-out ⤢)
    // rather than always landing as a disconnected `root`. The lookup reuses
    // the `onCanvas` flag from the neighbours query; if it finds nothing (or
    // fails), we place the node as a plain `root`. Placement itself never
    // blocks on the lookup failing.
    void connectNewNode(functionId)
      .catch(() => null)
      .then((origin) => {
        const node: ViewNodeUpsertRequest = origin
          ? {
              functionId,
              visible: true,
              originFunctionId: origin.originFunctionId,
              originKind: origin.originKind,
              originImplied: false,
            }
          : { functionId, visible: true, originKind: "root" };

        patchNodes.mutate(
          { upsert: [node] },
          {
            onSuccess: () => {
              canvasActions?.focusFunction(functionId);
            },
          },
        );
      });
  };

  return (
    <div>
      <input
        type="text"
        aria-label="Search functions"
        placeholder="Find or add function"
        value={text}
        disabled={binaryId === null || viewId === null}
        onChange={(e) => {
          setText(e.target.value);
        }}
        style={inputStyle}
      />
      {showResults && (
        <div style={resultsBoxStyle} role="listbox" aria-label="Function search results">
          {lookup.kind === "invalid" ? (
            <p role="alert" style={{ fontSize: "0.75rem", color: "#b91c1c", padding: "0.25rem 0.5rem", margin: 0 }}>
              {lookup.message}
            </p>
          ) : lookup.kind === "address" && address.isPending ? (
            <p style={{ fontSize: "0.75rem", color: "#6b7280", padding: "0.25rem 0.5rem", margin: 0 }}>
              Resolving {lookup.displayAddress}…
            </p>
          ) : lookup.kind === "address" && (address.isError || resolvedFunction === undefined) ? (
            <p role="alert" style={{ fontSize: "0.75rem", color: "#b91c1c", padding: "0.25rem 0.5rem", margin: 0 }}>
              No function could be resolved at {lookup.displayAddress}.
            </p>
          ) : lookup.kind === "address" ? (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              <li>
                <button
                  type="button"
                  role="option"
                  aria-selected={false}
                  disabled={patchNodes.isPending || view.isPending}
                  onClick={() => selectFunction(resolvedFunction!.id)}
                  style={rowButtonStyle}
                  title={onCanvasIds.has(resolvedFunction!.id)
                    ? `Jump to ${resolvedFunction!.displayName}`
                    : `Add ${resolvedFunction!.displayName} to the canvas`}
                >
                  <span className="gr-ground-truth">{resolvedFunction!.displayName}</span>
                  <span style={{ color: "#6b7280" }}>{toHex(resolvedFunction!.address)}</span>
                </button>
              </li>
            </ul>
          ) : search.isPending ? (
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
                    disabled={patchNodes.isPending || view.isPending}
                    onClick={() => {
                      selectFunction(row.id);
                    }}
                    style={rowButtonStyle}
                    title={onCanvasIds.has(row.id)
                      ? `Jump to ${row.displayName}`
                      : `Add ${row.displayName} to the canvas`}
                  >
                    <span className="gr-ground-truth">{row.displayName}</span>
                    <span style={{ color: "#6b7280" }}>{toHex(row.address)}</span>
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
