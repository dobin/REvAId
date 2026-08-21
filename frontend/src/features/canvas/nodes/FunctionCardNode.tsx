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
import type { FunctionId, ViewId, ViewNodeDto } from "@/api/types";
import { CardHeader } from "@/features/card/CardHeader";
import { CardSummary } from "@/features/card/CardSummary";
import { NeighbourTable } from "@/features/neighbours/NeighbourTable";
import { useAppStore } from "@/store";
import { useViewNodeActions } from "../useViewNodeActions";
import { CollapsedChip } from "./CollapsedChip";
import { ColorSwatchStrip } from "./ColorSwatchStrip";

/**
 * A card connects to its provenance parent/children vertically (layout
 * direction is DOWN, TAD §2.5) via a single unnamed source/target handle
 * pair — `deriveCanvasEdges` never targets a specific handle id, so every
 * render path (loading/error/collapsed/full) must render exactly this pair
 * or React Flow silently drops the edge (`Couldn't create edge for source
 * handle id: "null"`).
 */
function NodeHandles() {
  return (
    <>
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />
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
  const actions = useViewNodeActions(data.viewId);

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
        background: "white",
        border: "1px solid #d1d5db",
        borderRadius: "0.375rem",
        boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
        position: "relative",
      }}
    >
      <NodeHandles />
      <div style={{ display: "flex", alignItems: "center" }}>
        <div
          style={{ flex: 1, cursor: "pointer" }}
          onClick={() => {
            selectFunction(data.functionId);
          }}
        >
          <CardHeader fn={fn} />
        </div>
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
      <ColorSwatchStrip
        palette={config.nodeColorPalette}
        selected={data.viewNode.color}
        onSelect={(color) => {
          actions.setColor(data.functionId, color);
        }}
      />
      <CardSummary fn={fn} />
      <div style={{ padding: "0 0.75rem 0.75rem" }}>
        <NeighbourTable functionId={data.functionId} viewId={data.viewId} direction="callees" />
        <NeighbourTable functionId={data.functionId} viewId={data.viewId} direction="callers" />
      </div>
    </div>
  );
}
