/**
 * The canvas (TAD §2.3, I6). Renders every `visible` node of the given
 * `viewId` as a draggable `FunctionCardNode`, persists positions/camera,
 * derives edges from provenance only (D8b), and runs ELK layout for
 * newly-added, non-pinned nodes (D11, D15).
 */
import { useEffect, useMemo, useRef } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
  type Edge,
  type EdgeTypes,
  type Node,
  type NodeTypes,
  type OnNodeDrag,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useConfig } from "@/config/ConfigProvider";
import { usePatchViewMutation, useViewQuery } from "@/api/queries/views";
import { usePatchViewNodesMutation } from "@/api/queries/viewNodes";
import type { BinaryId, FunctionId, ViewId } from "@/api/types";
import { useAppStore } from "@/store";
import { CanvasActionsProvider, type FanOutOrigin } from "./CanvasActions";
import { CanvasEmptyState } from "./CanvasEmptyState";
import { useElkLayout } from "./layout/useElkLayout";
import { ProvenanceEdge } from "./edges/ProvenanceEdge";
import { FunctionCardNode, type FunctionCardNodeData } from "./nodes/FunctionCardNode";
import { deriveCanvasEdges } from "./selectors/deriveCanvasEdges";

const NODE_TYPES: NodeTypes = { functionCard: FunctionCardNode };
const EDGE_TYPES: EdgeTypes = { provenance: ProvenanceEdge };

/** Approximate card height before React Flow measures the real one —
 * only used as ELK's initial input for a node not yet rendered. */
const ESTIMATED_CARD_HEIGHT_PX = 240;

export function CanvasView({
  selectedBinaryId,
  viewId,
  actionsRegistry,
}: {
  selectedBinaryId: BinaryId | null;
  viewId: ViewId | null;
  actionsRegistry: React.MutableRefObject<import("./CanvasActions").CanvasActions | null>;
}) {
  if (selectedBinaryId === null || viewId === null) {
    return <CanvasEmptyState message="Pick a binary from the toolbar to get started." />;
  }
  return (
    <ReactFlowProvider>
      <CanvasViewInner viewId={viewId} actionsRegistry={actionsRegistry} />
    </ReactFlowProvider>
  );
}

function CanvasViewInner({
  viewId,
  actionsRegistry,
}: {
  viewId: ViewId;
  actionsRegistry: React.MutableRefObject<import("./CanvasActions").CanvasActions | null>;
}) {
  const config = useConfig();
  const view = useViewQuery(viewId);
  const patchNodes = usePatchViewNodesMutation(viewId);
  const patchView = usePatchViewMutation(viewId);
  const { positions, hydrateFromView, setDragPosition, commitDragAsPinned, upsertPosition } =
    useAppStore();
  const { runLayout, positions: elkPositions } = useElkLayout();
  const reactFlow = useReactFlow();
  const hydratedForViewId = useRef<ViewId | null>(null);

  useEffect(() => {
    if (!view.data || hydratedForViewId.current === viewId) return;
    hydrateFromView(view.data.nodes);
    hydratedForViewId.current = viewId;
  }, [view.data, viewId, hydrateFromView]);

  const visibleNodes = useMemo(
    () => (view.data ? view.data.nodes.filter((n) => n.visible) : []),
    [view.data],
  );
  const canvasEdges = useMemo(() => deriveCanvasEdges(visibleNodes), [visibleNodes]);

  const derivedNodes = useMemo<Node<FunctionCardNodeData>[]>(
    () =>
      visibleNodes.map((n) => {
        const pos = positions[n.functionId];
        const elkPos = elkPositions[String(n.functionId)];
        // A node mid-drag (or already pinned) must keep following its live
        // store position — falling back to `elkPos` here (which never
        // changes during a drag gesture) is what froze "virgin" unpinned
        // cards in place for their very first drag: the effect below
        // re-derives `rfNodes` from this on every `setDragPosition` frame,
        // stomping React Flow's own optimistic move with the same stale
        // ELK coordinate until `pinned` flips true on drag-stop.
        const position =
          pos?.dragging || pos?.pinned
            ? { x: pos.posX, y: pos.posY }
            : elkPos ?? { x: pos?.posX ?? n.posX, y: pos?.posY ?? n.posY };
        return {
          id: String(n.functionId),
          type: "functionCard",
          position,
          draggable: true,
          data: { functionId: n.functionId, viewId, viewNode: n },
        };
      }),
    [visibleNodes, positions, elkPositions, viewId],
  );

  // Controlled node state via React Flow's own recommended pattern
  // (`useNodesState` + `onNodesChange`, TAD §2.5's `useNodesInitialized`
  // sits on top of this same mechanism): this is the ONLY way a node's
  // measured width/height survives across re-renders. `<ReactFlow>` reports
  // dimension changes (from its internal `ResizeObserver`) as `NodeChange`
  // events through `onNodesChange`; those changes must be applied to
  // *persistent* React state via `applyNodeChanges`, or every re-render
  // that produces a new `derivedNodes` array (any position/data change)
  // silently drops the previously-measured `measured.height` back to
  // `undefined` — which is what caused new, especially tall, cards to be
  // laid out against a stale/estimated height and visually overlap their
  // neighbour. Whenever the *derived* node set changes (new node added or
  // removed, or its position moves), that is merged into the controlled
  // state while carrying each existing node's `measured` field forward.
  const [rfNodes, setRfNodes, onNodesChange] = useNodesState<Node<FunctionCardNodeData>>([]);
  useEffect(() => {
    setRfNodes((current) => {
      const measuredById = new Map(current.map((n) => [n.id, n.measured]));
      return derivedNodes.map((n) => {
        const measured = measuredById.get(n.id);
        return measured ? { ...n, measured } : n;
      });
    });
  }, [derivedNodes, setRfNodes]);

  const flowEdges = useMemo<Edge[]>(
    () =>
      canvasEdges.map((e) => ({
        id: e.id,
        source: String(e.source),
        target: String(e.target),
        type: "provenance",
        data: { implied: e.implied },
      })),
    [canvasEdges],
  );

  // Re-run ELK layout whenever the set of node ids changes (node
  // added/removed) using each node's real measured height where React Flow
  // already has one (a card can easily be 400-600px+ with expanded
  // tables); a brand-new, not-yet-rendered node falls back to
  // `ESTIMATED_CARD_HEIGHT_PX` for that first pass, then gets corrected
  // once `rfNodes` picks up its real `measured.height` from
  // `onNodesChange` and this effect re-runs (D11/§2.5's two-pass layout).
  // Never runs on a summary arrival (T1) — nothing here reacts to
  // `summary_status`.
  //
  // Heights are *bucketed* into `layoutHeightChangeThresholdPx` bands before
  // going into the key (§2.5's "> 8px" trigger rule): a card grows through
  // many intermediate heights as its summary/tables stream in, and keying on
  // the raw pixel value re-runs layout on every one of them, which both
  // thrashes and makes the cards visibly jitter.
  const layoutKey = rfNodes
    .map((n) => {
      const height = n.measured?.height;
      const bucket =
        height === undefined
          ? ""
          : Math.round(height / config.layoutHeightChangeThresholdPx);
      return `${n.id}:${String(bucket)}`;
    })
    .join(",");
  useEffect(() => {
    if (rfNodes.length === 0) return;
    runLayout(
      rfNodes.map((n) => ({
        id: n.id,
        width: config.cardWidthPx,
        height: n.measured?.height ?? ESTIMATED_CARD_HEIGHT_PX,
        pinned: positions[Number(n.id)]?.pinned ?? false,
        // A pinned node keeps the position it was dragged to; ELK needs it as
        // an obstacle so the block it lays out doesn't land on top of it.
        x: n.position.x,
        y: n.position.y,
      })),
      canvasEdges.map((e) => ({
        id: e.id,
        source: String(e.source),
        target: String(e.target),
      })),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed on layoutKey (node id set + bucketed measured heights) per D11's trigger rules, not every position/edge object identity change.
  }, [layoutKey]);

  const handleNodeDragStop: OnNodeDrag = (_event, node) => {
    const functionId: FunctionId = Number(node.id);
    commitDragAsPinned(functionId, node.position.x, node.position.y);
    patchNodes.mutate({
      upsert: [{ functionId, posX: node.position.x, posY: node.position.y, pinned: true }],
    });
  };

  const handleNodeDrag: OnNodeDrag = (_event, node) => {
    const functionId: FunctionId = Number(node.id);
    setDragPosition(functionId, node.position.x, node.position.y);
  };

  const handleMoveEnd = (): void => {
    const { x, y, zoom } = reactFlow.getViewport();
    patchView.mutate({ camera: { x, y, zoom } });
  };

  const fanOutFunction = (origin: FanOutOrigin, functionId: FunctionId) => {
    const alreadyPresent = visibleNodes.some((n) => n.functionId === functionId);
    if (alreadyPresent) return;
    upsertPosition(functionId, 0, 0, false);
    // A row in the origin card's *callers* table spawns the new node as the
    // caller (`fanin`) — deriveCanvasEdges orients its edge so ELK lays it to
    // the left. A *callees* row spawns it as the callee (`fanout`, right).
    const originKind = origin.direction === "callers" ? "fanin" : "fanout";
    patchNodes.mutate({
      upsert: [
        {
          functionId,
          visible: true,
          originFunctionId: origin.functionId,
          originKind,
          originImplied: false,
        },
      ],
    });
  };

  const focusFunction = (functionId: FunctionId): void => {
    const node = rfNodes.find((n) => n.id === String(functionId));
    if (!node) return;
    const width = node.measured?.width ?? config.cardWidthPx;
    const height = node.measured?.height ?? ESTIMATED_CARD_HEIGHT_PX;
    void reactFlow.fitBounds(
      {
        x: node.position.x,
        y: node.position.y,
        width,
        height,
      },
      { duration: 400, padding: 0.3 },
    );
  };

  const hideFunction = (functionId: FunctionId): void => {
    patchNodes.mutate({ upsert: [{ functionId, visible: false }] });
  };

  // Register current actions into the stable ref so components outside this
  // provider tree (e.g. Sidebar) can call them via useCanvasActionsFromRegistry.
  actionsRegistry.current = { fanOutFunction, focusFunction, hideFunction };

  if (view.isPending) {
    return <CanvasEmptyState message="Loading…" />;
  }
  if (view.isError) {
    return <CanvasEmptyState message="Could not load this view." />;
  }
  if (rfNodes.length === 0) {
    return <CanvasEmptyState message="Nothing placed on this view yet. Search for a function to get started." />;
  }

  return (
    <CanvasActionsProvider value={{ fanOutFunction, focusFunction, hideFunction }}>
      <div style={{ width: "100%", height: "100%" }}>
        <ReactFlow
          nodes={rfNodes}
          edges={flowEdges}
          nodeTypes={NODE_TYPES}
          edgeTypes={EDGE_TYPES}
          onNodesChange={onNodesChange}
          fitView
          fitViewOptions={{ maxZoom: 1.0 }}
          minZoom={0.05}
          nodesDraggable
          defaultViewport={{
            x: view.data.camera.x,
            y: view.data.camera.y,
            zoom: view.data.camera.zoom,
          }}
          onNodeDrag={handleNodeDrag}
          onNodeDragStop={handleNodeDragStop}
          onMoveEnd={handleMoveEnd}
        />
      </div>
    </CanvasActionsProvider>
  );
}
