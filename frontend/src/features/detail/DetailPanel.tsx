/**
 * Minimal read-only detail panel (I6, pulled forward from I10's full
 * `DetailPanel`). Shows identity/address/kind/signature/fan counts for the
 * currently selected function. Ground-truth code is intentionally shown here
 * rather than on a canvas card, where it would make the graph unreadable.
 */
import { useEffect, useRef, useState } from "react";
import { useFunctionQuery } from "@/api/queries/functions";
import { useInfiniteNeighboursQuery } from "@/api/queries/neighbours";
import type { FunctionId, ViewId } from "@/api/types";
import { toHex } from "@/lib/hex";
import { useAppStore } from "@/store";

const DETAIL_PANEL_WIDTH_KEY = "graphrev.detailPanelWidth";
const DEFAULT_PANEL_WIDTH = 672;
const MIN_PANEL_WIDTH = 280;
const MAX_PANEL_WIDTH = 960;

function readPanelWidth(): number {
  try {
    const saved = Number(window.localStorage.getItem(DETAIL_PANEL_WIDTH_KEY));
    return Number.isFinite(saved) && saved >= MIN_PANEL_WIDTH && saved <= MAX_PANEL_WIDTH
      ? saved
      : DEFAULT_PANEL_WIDTH;
  } catch {
    return DEFAULT_PANEL_WIDTH;
  }
}

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

function NeighbourList({
  functionId,
  viewId,
  direction,
}: {
  functionId: FunctionId;
  viewId: ViewId | null;
  direction: "callees" | "callers";
}) {
  const enabled = viewId !== null;
  const queryParams = {
    functionId,
    viewId: viewId ?? 0,
    direction,
    group: "primary" as const,
    enabled,
  };
  const primary = useInfiniteNeighboursQuery(queryParams);
  const utility = useInfiniteNeighboursQuery({ ...queryParams, group: "utility" });

  useEffect(() => {
    if (primary.hasNextPage && !primary.isFetchingNextPage) void primary.fetchNextPage();
  }, [primary.hasNextPage, primary.isFetchingNextPage, primary.fetchNextPage]);
  useEffect(() => {
    if (utility.hasNextPage && !utility.isFetchingNextPage) void utility.fetchNextPage();
  }, [utility.hasNextPage, utility.isFetchingNextPage, utility.fetchNextPage]);

  const label = direction === "callees" ? "Callees" : "Callers";
  const primaryFirstPage = primary.data?.pages[0];
  const utilityFirstPage = utility.data?.pages[0];
  const rows = [
    ...(primary.data?.pages.flatMap((page) => page.rows) ?? []),
    ...(utility.data?.pages.flatMap((page) => page.rows) ?? []),
  ];

  return (
    <section style={{ marginTop: "1rem" }}>
      <h3 style={{ fontSize: "0.875rem", margin: "0 0 0.25rem" }}>{label}</h3>
      {!enabled ? (
        <p style={{ color: "#6b7280", fontSize: "0.8125rem" }}>No view available.</p>
      ) : primary.isPending || utility.isPending ? (
        <p>Loading {label.toLowerCase()}…</p>
      ) : primary.isError || utility.isError ? (
        <p>Could not load {label.toLowerCase()}.</p>
      ) : primaryFirstPage?.callersSuppressed || utilityFirstPage?.callersSuppressed ? (
        <p style={{ color: "#6b7280", fontSize: "0.8125rem" }}>
          Caller list suppressed ({primaryFirstPage?.total ?? utilityFirstPage?.total}).
        </p>
      ) : rows.length === 0 ? (
        <p style={{ color: "#6b7280", fontSize: "0.8125rem" }}>None</p>
      ) : (
        <ul style={{ fontSize: "0.8125rem", margin: 0, paddingLeft: "1.25rem" }}>
          {rows.map((row) => (
            <li key={row.id} className="gr-ground-truth">{row.displayName}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function DetailPanel({ viewId }: { viewId: ViewId | null }) {
  const selectedFunctionId = useAppStore((s) => s.selectedFunctionId);
  const clearSelection = useAppStore((s) => s.clearSelection);
  const [panelWidth, setPanelWidth] = useState(readPanelWidth);
  const [resizing, setResizing] = useState(false);
  const dragStart = useRef<{ pointerX: number; width: number } | null>(null);
  const { data: fn, isPending, isError } = useFunctionQuery(selectedFunctionId);

  useEffect(() => {
    try {
      window.localStorage.setItem(DETAIL_PANEL_WIDTH_KEY, String(panelWidth));
    } catch {
      // Keep resizing usable when browser storage is unavailable.
    }
  }, [panelWidth]);

  useEffect(() => {
    if (!resizing) return;
    const move = (event: PointerEvent) => {
      const start = dragStart.current;
      if (!start) return;
      setPanelWidth(Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, start.width + start.pointerX - event.clientX)));
    };
    const stop = () => {
      dragStart.current = null;
      setResizing(false);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
  }, [resizing]);

  if (selectedFunctionId === null) return null;

  return (
    <aside
      style={{
        width: `${String(panelWidth)}px`,
        minWidth: 0,
        flexShrink: 0,
        position: "relative",
        overflowY: "auto",
        padding: "1rem",
        borderLeft: "1px solid #e5e7eb",
      }}
      aria-label="Function detail"
    >
      <div
        role="separator"
        aria-label="Resize function details panel"
        aria-orientation="vertical"
        aria-valuemin={MIN_PANEL_WIDTH}
        aria-valuemax={MAX_PANEL_WIDTH}
        aria-valuenow={panelWidth}
        tabIndex={0}
        onPointerDown={(event) => {
          event.preventDefault();
          dragStart.current = { pointerX: event.clientX, width: panelWidth };
          setResizing(true);
        }}
        onKeyDown={(event) => {
          if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
          event.preventDefault();
          const delta = event.key === "ArrowLeft" ? 16 : -16;
          setPanelWidth((width) => Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, width + delta)));
        }}
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: 0,
          width: "6px",
          cursor: "col-resize",
          touchAction: "none",
          zIndex: 1,
        }}
      />
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
          <NeighbourList functionId={fn.id} viewId={viewId} direction="callers" />
          <NeighbourList functionId={fn.id} viewId={viewId} direction="callees" />
        </div>
      )}
    </aside>
  );
}
