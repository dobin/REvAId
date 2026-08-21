/**
 * The canvas (TAD §2.3). I5 scope: resolve the binary's first view and its
 * top entry point, then render exactly one `FunctionCardNode` at a fixed
 * position. No ELK layout (single node), no fan-out, no persistence — all
 * of that is I6.
 */
import { useMemo } from "react";
import { ReactFlow, type Node, type NodeTypes } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEntryPointsQuery } from "@/api/queries/binaries";
import { useViewsQuery } from "@/api/queries/views";
import type { BinaryId } from "@/api/types";
import { CanvasEmptyState } from "./CanvasEmptyState";
import { FunctionCardNode, type FunctionCardNodeData } from "./nodes/FunctionCardNode";

const NODE_TYPES: NodeTypes = { functionCard: FunctionCardNode };

export function CanvasView({ selectedBinaryId }: { selectedBinaryId: BinaryId | null }) {
  const entryPoints = useEntryPointsQuery(selectedBinaryId);
  const views = useViewsQuery(selectedBinaryId);

  const nodes = useMemo<Node<FunctionCardNodeData>[]>(() => {
    const topEntryPoint = entryPoints.data?.entryPoints[0];
    const firstView = views.data?.[0];
    if (!topEntryPoint || !firstView) return [];
    return [
      {
        id: String(topEntryPoint.id),
        type: "functionCard",
        position: { x: 0, y: 0 },
        data: { functionId: topEntryPoint.id, viewId: firstView.id },
      },
    ];
  }, [entryPoints.data, views.data]);

  if (selectedBinaryId === null) {
    return <CanvasEmptyState message="Pick a binary from the toolbar to get started." />;
  }

  if (entryPoints.isPending || views.isPending) {
    return <CanvasEmptyState message="Loading…" />;
  }

  if (entryPoints.isError || views.isError) {
    return <CanvasEmptyState message="Could not load this binary's canvas." />;
  }

  if (nodes.length === 0) {
    return <CanvasEmptyState message="This binary has no entry-point suggestions yet." />;
  }

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ReactFlow nodes={nodes} edges={[]} nodeTypes={NODE_TYPES} fitView nodesDraggable={false} />
    </div>
  );
}
