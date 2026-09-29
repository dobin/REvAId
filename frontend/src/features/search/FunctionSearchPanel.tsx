import { useMemo, useState } from "react";
import { useFunctionAddressQuery, useFunctionSearchQuery } from "@/api/queries/binaries";
import { usePatchViewNodesMutation } from "@/api/queries/viewNodes";
import { useViewQuery } from "@/api/queries/views";
import type { BinaryId, FunctionSearchRowDto, ViewId, ViewNodeUpsertRequest } from "@/api/types";
import { useCanvasActionsFromRegistry } from "@/features/canvas/CanvasActions";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { resolveAddressLookup } from "@/lib/address";
import { toHex } from "@/lib/hex";
import { useConnectNewNode } from "@/features/sidebar/useConnectNewNode";
import { RuntimeBaseControl } from "@/features/sidebar/RuntimeBaseControl";
import { useAppStore } from "@/store";

const PAGE_SIZE = 50;

export function FunctionSearchPanel({
  binaryId,
  viewId,
  analysisImageBase,
  runtimeBase,
  onRuntimeBaseChange,
  focusCanvas = true,
  onOpenExisting,
  onAdded,
}: {
  binaryId: BinaryId;
  viewId: ViewId | null;
  analysisImageBase: number | null;
  runtimeBase: number | null;
  onRuntimeBaseChange?: (value: number | null) => void;
  focusCanvas?: boolean;
  onOpenExisting?: (functionId: number) => void;
  onAdded?: () => void;
}) {
  const [text, setText] = useState("");
  const [offset, setOffset] = useState(0);
  const [hoveredCodeRow, setHoveredCodeRow] = useState<number | null>(null);
  const [expandedCodeRows, setExpandedCodeRows] = useState<Set<number>>(() => new Set());
  const debounced = useDebouncedValue(text, 250);
  const lookup = resolveAddressLookup(debounced, runtimeBase, analysisImageBase);
  const view = useViewQuery(viewId);
  const search = useFunctionSearchQuery(binaryId, lookup.kind === "text" ? debounced : "", offset);
  const address = useFunctionAddressQuery(
    binaryId,
    lookup.kind === "address" ? lookup.canonicalAddress : null,
  );
  const patchNodes = usePatchViewNodesMutation(viewId ?? 0);
  const canvasActions = useCanvasActionsFromRegistry();
  const connectNewNode = useConnectNewNode(viewId);
  const selectFunction = useAppStore((state) => state.selectFunction);
  const onCanvasIds = useMemo(() => {
    const ids = new Set<number>();
    for (const node of view.data?.nodes ?? []) if (node.visible) ids.add(node.functionId);
    return ids;
  }, [view.data]);

  const addressRow: FunctionSearchRowDto | null = address.data
    ? {
        id: address.data.id,
        address: address.data.address,
        displayName: address.data.displayName,
        isRenamed: address.data.nameAnalyst !== null,
        kind: address.data.kind,
        isUtility: address.data.isUtility,
        fanIn: address.data.fanIn,
        hasNotes: Boolean(address.data.notes),
        isEntryPoint: Boolean(address.data.isEntryPoint),
        codeMatches: [],
        codeMatchesTruncated: false,
      }
    : null;
  const rows = lookup.kind === "address" ? (addressRow ? [addressRow] : []) : search.data?.rows ?? [];

  const addOrFocus = (functionId: number) => {
    if (viewId === null || patchNodes.isPending) return;
    if (onCanvasIds.has(functionId)) {
      if (onOpenExisting) {
        onOpenExisting(functionId);
        return;
      }
      if (focusCanvas) canvasActions?.focusFunction(functionId);
      return;
    }
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
              if (focusCanvas) canvasActions?.focusFunction(functionId);
              selectFunction(functionId);
              onAdded?.();
            },
          },
        );
      });
  };

  const showResults = debounced.trim().length > 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", minHeight: 0 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem" }}>
      <label style={{ display: "block", flex: "1 1 0", minWidth: 0, fontSize: "0.8125rem", fontWeight: 600 }}>
        Search functions by name, address, notes, or decompiled C
        <input
          type="search"
          aria-label="Search functions"
          placeholder="Name, 0x address, or C code…"
          value={text}
          disabled={viewId === null}
          onChange={(event) => {
            setText(event.target.value);
            setOffset(0);
          }}
          style={{ display: "block", width: "100%", boxSizing: "border-box", marginTop: "0.35rem", padding: "0.55rem 0.65rem", border: "1px solid #cbd5e1", borderRadius: "0.375rem", fontSize: "0.9rem" }}
        />
      </label>
      {onRuntimeBaseChange && (
        <RuntimeBaseControl
          analysisImageBase={analysisImageBase}
          runtimeBase={runtimeBase}
          onRuntimeBaseChange={onRuntimeBaseChange}
        />
      )}
      </div>
      {!showResults ? (
        <p style={{ color: "#6b7280", margin: 0, fontSize: "0.85rem" }}>Search addresses, function names, notes, or text in C decompilation.</p>
      ) : lookup.kind === "invalid" ? (
        <p role="alert" style={{ color: "#b91c1c", margin: 0 }}>{lookup.message}</p>
      ) : lookup.kind === "address" && address.isPending ? (
        <p role="status" style={{ color: "#6b7280", margin: 0 }}>Resolving {lookup.displayAddress}…</p>
      ) : lookup.kind === "address" && address.isError ? (
        <p role="alert" style={{ color: "#b91c1c", margin: 0 }}>No function could be resolved at {lookup.displayAddress}.</p>
      ) : lookup.kind === "text" && search.isPending ? (
        <p role="status" style={{ color: "#6b7280", margin: 0 }}>Searching…</p>
      ) : rows.length === 0 ? (
        <p style={{ color: "#6b7280", margin: 0 }}>No matches.</p>
      ) : (
        <>
          <div style={{ overflow: "auto", border: "1px solid #e5e7eb", borderRadius: "0.375rem" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem" }}>
              <thead><tr style={{ textAlign: "left", background: "#f9fafb" }}>
                <th style={cellStyle}>Function</th>
                <th style={cellStyle}>Address</th>
                <th style={cellStyle}>C matches</th>
                <th style={cellStyle}><span className="sr-only">Action</span></th>
              </tr></thead>
              <tbody>
                {rows.map((row) => {
                  const onCanvas = onCanvasIds.has(row.id);
                  const actionName = `${onCanvas ? "Open" : "Add"} ${row.displayName}${onCanvas ? " on canvas" : " to canvas"}`;
                  return (
                    <tr
                      key={row.id}
                      tabIndex={0}
                      aria-label={actionName}
                      onClick={() => { addOrFocus(row.id); }}
                      onKeyDown={(event) => {
                        if (event.target !== event.currentTarget) return;
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          addOrFocus(row.id);
                        }
                      }}
                      style={{ cursor: "pointer" }}
                    >
                    <td style={cellStyle}>
                      <strong>{row.displayName}</strong>
                      <div style={{ color: "#6b7280", marginTop: "0.2rem" }}>{row.kind}{row.isEntryPoint ? " · entry point" : ""}{row.hasNotes ? " · notes" : ""}</div>
                    </td>
                    <td style={{ ...cellStyle, whiteSpace: "nowrap", fontFamily: "ui-monospace, monospace" }}>{toHex(row.address)}</td>
                    <td
                      style={{ ...cellStyle, minWidth: "18rem" }}
                      onMouseEnter={() => { setHoveredCodeRow(row.id); }}
                      onMouseLeave={() => {
                        setHoveredCodeRow((current) => current === row.id ? null : current);
                      }}
                    >
                      {row.codeMatches.length ? (
                        <details
                          open={hoveredCodeRow === row.id || expandedCodeRows.has(row.id)}
                          onClick={(event) => { event.stopPropagation(); }}
                        >
                          <summary
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              setExpandedCodeRows((current) => {
                                const next = new Set(current);
                                if (next.has(row.id)) next.delete(row.id);
                                else next.add(row.id);
                                return next;
                              });
                            }}
                            style={{ color: "#475569", cursor: "pointer" }}
                          >
                            {row.codeMatchesTruncated ? `${String(row.codeMatches.length)}+` : row.codeMatches.length} matching {row.codeMatches.length === 1 && !row.codeMatchesTruncated ? "line" : "lines"}
                          </summary>
                          <div style={{ display: "grid", gap: "0.25rem", marginTop: "0.5rem" }}>
                            {row.codeMatches.map((match) => <div key={match.lineNumber} style={{ display: "flex", gap: "0.5rem", fontFamily: "ui-monospace, monospace", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                              <span style={{ color: "#6b7280", userSelect: "none" }}>{match.lineNumber}</span><span>{match.text}</span>
                            </div>)}
                            {row.codeMatchesTruncated && <span style={{ color: "#92400e" }}>More matching lines not shown (20-line limit).</span>}
                          </div>
                        </details>
                      ) : <span style={{ color: "#9ca3af" }}>—</span>}
                    </td>
                    <td style={{ ...cellStyle, whiteSpace: "nowrap", textAlign: "right" }}>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          addOrFocus(row.id);
                        }}
                        disabled={patchNodes.isPending || view.isPending || viewId === null}
                        aria-label={onCanvas ? `Open ${row.displayName}` : `Add ${row.displayName} to canvas`}
                        title={onCanvas ? "Already on canvas — open in the detail panel" : "Add to canvas"}
                        style={{
                          border: "1px solid #cbd5e1",
                          borderRadius: "0.375rem",
                          padding: "0.35rem 0.75rem",
                          background: onCanvas ? "#f8fafc" : "#eff6ff",
                          color: onCanvas ? "#334155" : "#1d4ed8",
                          fontSize: "0.8125rem",
                          fontWeight: 600,
                          cursor: patchNodes.isPending || view.isPending || viewId === null ? "not-allowed" : "pointer",
                        }}
                      >
                        {onCanvas ? "Open" : "Add"}
                      </button>
                    </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {lookup.kind === "text" && search.data && <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.8125rem" }}>
            <span>{search.data.total} function{search.data.total === 1 ? "" : "s"} found</span>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button type="button" disabled={offset === 0} onClick={() => { setOffset(Math.max(0, offset - PAGE_SIZE)); }}>Previous</button>
              <button type="button" disabled={offset + rows.length >= search.data.total} onClick={() => { setOffset(offset + PAGE_SIZE); }}>Next</button>
            </div>
          </div>}
          {patchNodes.isError && <p role="alert" style={{ color: "#b91c1c", margin: 0 }}>Could not add the function to this view.</p>}
        </>
      )}
    </div>
  );
}

const cellStyle: React.CSSProperties = {
  padding: "0.6rem",
  borderBottom: "1px solid #e5e7eb",
  verticalAlign: "top",
}
