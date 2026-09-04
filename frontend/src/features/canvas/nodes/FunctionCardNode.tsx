/**
 * React Flow custom node — the function card (TAD §2.3/§4.3). Composes
 * `CardHeader` + `CardSummary` + both `NeighbourTable`s. I6 adds: a ✕ hide
 * button (D13, patches `visible:false`), an inline colour-swatch strip
 * (D16, minimal — no dropdown menu, that's I10), click-to-select for the
 * detail panel, and rendering `CollapsedChip` instead of the full body when
 * `viewNode.collapsed` is true (D14).
 */
import { Handle, Position } from "@xyflow/react";
import { useConfig } from "@/config/ConfigProvider";
import { useFunctionQuery } from "@/api/queries/functions";
import { useRegenerateSummaryMutation } from "@/api/queries/summaries";
import type { FunctionId, ViewId, ViewNodeDto } from "@/api/types";
import { CardHeader } from "@/features/card/CardHeader";
import { CardSummary } from "@/features/card/CardSummary";
import { NeighbourTable } from "@/features/neighbours/NeighbourTable";
import { useSummaryDemand } from "@/hooks/useSummaryDemand";
import { Glyph } from "@/components/Glyph";
import { useAppStore } from "@/store";
import { useViewNodeActions } from "../useViewNodeActions";
import { CollapsedChip } from "./CollapsedChip";
import { SWATCH_HEX } from "./ColorSwatchStrip";

/**
 * A card connects to its provenance parent/children horizontally (layout
 * direction is RIGHT, TAD §2.5 — a callee sits to the right of its caller)
 * via a single unnamed source/target handle pair — `deriveCanvasEdges`
 * never targets a specific handle id, so every render path
 * (loading/error/collapsed/full) must render exactly this pair or React Flow
 * silently drops the edge (`Couldn't create edge for source handle id:
 * "null"`).
 */
function NodeHandles() {
  return (
    <>
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
    </>
  );
}

export interface FunctionCardNodeData extends Record<string, unknown> {
  functionId: FunctionId;
  viewId: ViewId;
  viewNode: ViewNodeDto;
}

export function FunctionCardNode({ data }: { data: FunctionCardNodeData }) {
  const config = useConfig();
  const { data: fn, isPending, isError } = useFunctionQuery(data.functionId);
  const selectFunction = useAppStore((s) => s.selectFunction);
  const clearSelection = useAppStore((s) => s.clearSelection);
  const isSelected = useAppStore((s) => s.selectedFunctionId === data.functionId);
  const actions = useViewNodeActions(data.viewId);
  const regenerateSummary = useRegenerateSummaryMutation();

  // I9 §5.1: opening/placing a card demands its OWN summary at priority 0,
  // ahead of anything in its tables (priority 1/2) — "analyse the function
  // itself first". Suppressed while collapsed (D14) since a collapsed card
  // shows no summary at all (mirrors the C2b "deferred, not skipped" rule).
  useSummaryDemand({
    surface: `card:${String(data.functionId)}`,
    functionIds: [data.functionId],
    priority: 0,
    enabled: !data.viewNode.collapsed,
  });

  if (isPending) {
    return (
      <div style={{ width: config.cardWidthPx, background: "white", padding: "0.75rem" }}>
        <NodeHandles />
        Loading function…
      </div>
    );
  }
  if (isError) {
    return (
      <div style={{ width: config.cardWidthPx, background: "white", padding: "0.75rem" }}>
        <NodeHandles />
        Could not load function.
      </div>
    );
  }

  if (data.viewNode.collapsed) {
    return (
      <div style={{ position: "relative" }}>
        <NodeHandles />
        <CollapsedChip
          fn={fn}
          onExpand={() => {
            actions.setCollapsed(data.functionId, false);
          }}
        />
      </div>
    );
  }

  return (
    <div
      style={{
        width: config.cardWidthPx,
        background: data.viewNode.color ? SWATCH_HEX[data.viewNode.color] : "white",
        border: "1px solid #d1d5db",
        borderRadius: "0.375rem",
        boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
        position: "relative",
      }}
    >
      <NodeHandles />
      <div style={{ display: "flex", alignItems: "center" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <CardHeader
            fn={fn}
            color={data.viewNode.color}
            palette={config.nodeColorPalette}
            onColorSelect={(color) => {
              actions.setColor(data.functionId, color);
            }}
          />
        </div>
        <button
          type="button"
          aria-label={`Refresh summary for ${fn.displayName}`}
          title="Refresh summary"
          onClick={() => {
            regenerateSummary.mutate(data.functionId);
          }}
          disabled={regenerateSummary.isPending}
          style={{
            border: "none",
            background: "none",
            borderRadius: "0.25rem",
            cursor: regenerateSummary.isPending ? "default" : "pointer",
            padding: "0.375rem 0.5rem",
            color: "#6b7280",
          }}
        >
          <Glyph name="retry" />
        </button>
        <button
          type="button"
          aria-label={isSelected ? `Hide details for ${fn.displayName}` : `Show details for ${fn.displayName}`}
          aria-pressed={isSelected}
          title={isSelected ? "Hide details" : "Show details"}
          onClick={() => {
            if (isSelected) {
              clearSelection();
            } else {
              selectFunction(data.functionId);
            }
          }}
          style={{
            border: "none",
            background: isSelected ? "#e5e7eb" : "none",
            borderRadius: "0.25rem",
            cursor: "pointer",
            padding: "0.375rem 0.5rem",
            color: isSelected ? "#111827" : "#6b7280",
          }}
        >
          ℹ
        </button>
        <button
          type="button"
          aria-label={`Hide ${fn.displayName}`}
          title="Hide"
          onClick={() => {
            actions.setVisible(data.functionId, false);
          }}
          style={{
            border: "none",
            background: "none",
            cursor: "pointer",
            padding: "0.5rem 0.75rem",
          }}
        >
          ✕
        </button>
      </div>
      <CardSummary fn={fn} />
      <div style={{ padding: "0 0.75rem 0.75rem" }}>
        <NeighbourTable functionId={data.functionId} viewId={data.viewId} direction="callees" />
        <NeighbourTable functionId={data.functionId} viewId={data.viewId} direction="callers" />
      </div>
    </div>
  );
}
