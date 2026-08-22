/**
 * The canvas (TAD §2.3, I6). Renders every `visible` node of the given
 * `viewId` as a draggable `FunctionCardNode`, persists positions/camera,
 * derives edges from provenance only (D8b), and runs ELK layout for
 * newly-added, non-pinned nodes (D11, D15).
 */
import { useEffect, useMemo, useRef, useState } from "react";
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
import { useQueryClient } from "@tanstack/react-query";
import { useConfig } from "@/config/ConfigProvider";
import { functionQueryOptions } from "@/api/queries/functions";
import { neighbourQueryOptions } from "@/api/queries/neighbours";
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
  const queryClient = useQueryClient();
  const view = useViewQuery(viewId);
  const patchNodes = usePatchViewNodesMutation(viewId);
  const patchView = usePatchViewMutation(viewId);
  const { positions, hydrateFromView, setDragPosition, commitDragAsPinned, upsertPosition } =
    useAppStore();
  const {
    runLayout,
    positions: elkPositions,
    isLayoutPending,
    isLayoutPendingRef,
  } = useElkLayout();
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

  // ---------------------------------------------------------------------
  // Reveal-after-layout (fixes the fan-out flicker).
  //
  // A freshly fanned-out node has no trustworthy position yet: the store
  // inserts it optimistically at (0,0) and the server echoes posX/posY 0,
  // which is *behind the origin card*. React Flow renders it hidden only
  // until it has been measured (`visibility: hasDimensions ? 'visible' :
  // 'hidden'` in its NodeWrapper) — and measurement completes strictly
  // BEFORE ELK can answer, because ELK is only *triggered* by the measured
  // height landing in `layoutKey` and then resolves asynchronously. So the
  // node's first visible frame is at (0,0), and it jumps to its real slot a
  // frame or two later. That is the flicker.
  //
  // The fix keeps RF's own mechanism and just extends it by one round trip:
  // a node that appeared after hydration is held at `visibility: hidden`
  // (still in normal flow, so the ResizeObserver measures it exactly as
  // before) until ELK has produced a position for it. `node.style` is
  // spread *after* RF's own `visibility` in NodeWrapper, so this overrides
  // it rather than fighting it.
  //
  // Nodes present at hydration are never gated: they already carry
  // persisted positions, so hiding them would flash the canvas blank on
  // every load.
  const seenNodeIdsRef = useRef<Set<string> | null>(null);
  const [awaitingLayoutIds, setAwaitingLayoutIds] = useState<ReadonlySet<string>>(new Set());

  useEffect(() => {
    if (!view.data) return;
    const ids = visibleNodes.map((n) => String(n.functionId));
    const seen = seenNodeIdsRef.current;
    if (seen === null) {
      seenNodeIdsRef.current = new Set(ids);
      return;
    }
    const fresh = ids.filter((id) => !seen.has(id));
    // Forget ids that left the canvas, so re-adding one gates it again.
    for (const id of [...seen]) {
      if (!ids.includes(id)) seen.delete(id);
    }
    for (const id of ids) seen.add(id);
    if (fresh.length === 0) return;
    console.debug("[canvas] holding new node(s) hidden until ELK layout:", fresh);
    setAwaitingLayoutIds((prev) => new Set([...prev, ...fresh]));
  }, [view.data, visibleNodes]);

  const derivedNodes = useMemo<Node<FunctionCardNodeData>[]>(
    () =>
      visibleNodes.map((n) => {
        const id = String(n.functionId);
        const pos = positions[n.functionId];
        const elkPos = elkPositions[id];
        const awaitingLayout = awaitingLayoutIds.has(id);
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
          id,
          type: "functionCard",
          position,
          draggable: true,
          // Conditional spread, not `style: cond ? x : undefined` —
          // exactOptionalPropertyTypes rejects the latter.
          ...(awaitingLayout ? { style: { visibility: "hidden" as const } } : {}),
          data: { functionId: n.functionId, viewId, viewNode: n },
        };
      }),
    [visibleNodes, positions, elkPositions, awaitingLayoutIds, viewId],
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

  // An edge touching a gated node must be hidden too, or the connector line
  // is drawn to the node's (0,0) placeholder slot and flashes across the
  // canvas — exactly the artefact the gate exists to remove.
  const flowEdges = useMemo<Edge[]>(
    () =>
      canvasEdges.map((e) => {
        const source = String(e.source);
        const target = String(e.target);
        return {
          id: e.id,
          source,
          target,
          type: "provenance",
          hidden: awaitingLayoutIds.has(source) || awaitingLayoutIds.has(target),
          data: { implied: e.implied },
        };
      }),
    [canvasEdges, awaitingLayoutIds],
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

  // Release a gated node once ELK has a position for it that was computed
  // from its *real* measured height. Releasing on the first ELK answer is
  // not enough: layout pass 1 runs against `ESTIMATED_CARD_HEIGHT_PX`
  // (the node is not in the DOM yet), so revealing then would still show a
  // jump when pass 2 corrects it. Requiring both "ELK has a position" and
  // "React Flow has measured this node" means the position in hand came
  // from a pass that knew the true height.
  const measuredIds = useMemo(
    () =>
      new Set(rfNodes.filter((n) => n.measured?.height !== undefined).map((n) => n.id)),
    [rfNodes],
  );
  //
  // Also waits for `isLayoutPending` to clear: measuring a new card usually
  // nudges a neighbour's height bucket too, which queues another pass. If we
  // reveal while that pass is in flight, the node shows up at the previous
  // pass's coordinate and then shifts (~48px, one `nodeNode` gap, observed
  // live) once the newer result lands — a smaller version of the very jump
  // this gate exists to remove.
  useEffect(() => {
    if (isLayoutPendingRef.current) return;
    setAwaitingLayoutIds((prev) => {
      if (prev.size === 0) return prev;
      const next = new Set(
        [...prev].filter((id) => elkPositions[id] === undefined || !measuredIds.has(id)),
      );
      if (next.size === prev.size) return prev;
      console.debug(
        "[canvas] revealing node(s) at ELK position:",
        [...prev].filter((id) => !next.has(id)),
      );
      return next;
    });
  }, [elkPositions, measuredIds, isLayoutPending, isLayoutPendingRef]);

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

  // Prefetch-then-insert — fixes the *first*-fan-out flicker specifically.
  //
  // The reveal gate above opens as soon as a node has (a) an ELK position and
  // (b) *any* measured height. On a virgin fan-out that first measured height
  // is the `Loading function…` placeholder, not the real card: the
  // `useFunctionQuery`/`useNeighboursQuery` calls inside `FunctionCardNode`
  // are still pending on its first commit. So ELK lays out against the
  // placeholder height, the gate opens, and the card then grows to its real
  // 400-600px, crosses a height bucket, re-runs layout and visibly moves.
  //
  // Re-adding a previously-hidden node never shows this: hiding it unmounts
  // the component but leaves its TanStack Query entries in the cache, so the
  // second mount renders the *full* card synchronously and its first measured
  // height is already the final one. Warming that cache before the node
  // enters the view puts the first fan-out on the same path.
  //
  // Failure is deliberately non-fatal (`allSettled`, same handler both ways):
  // the node is inserted regardless and the card falls back to its own
  // loading state, so a failing request can never make fan-out silently
  // do nothing.
  const fanOutFunction = (origin: FanOutOrigin, functionId: FunctionId) => {
    const alreadyPresent = visibleNodes.some((n) => n.functionId === functionId);
    if (alreadyPresent) return;
    // A row in the origin card's *callers* table spawns the new node as the
    // caller (`fanin`) — deriveCanvasEdges orients its edge so ELK lays it to
    // the left. A *callees* row spawns it as the callee (`fanout`, right).
    const originKind = origin.direction === "callers" ? "fanin" : "fanout";

    const insert = (): void => {
      upsertPosition(functionId, 0, 0, false);
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

    // Exactly the queries `FunctionCardNode` mounts with, using exactly the
    // default params `NeighbourTable` uses on its first render — a differing
    // sort/filter would populate a *different* cache entry and warm nothing.
    // `UtilityGroup` is intentionally not prefetched: it only mounts when
    // expanded, so it cannot affect the initial measured height.
    void Promise.allSettled([
      queryClient.prefetchQuery(functionQueryOptions(functionId)),
      ...(["callees", "callers"] as const).map((direction) =>
        queryClient.prefetchQuery(
          neighbourQueryOptions({
            functionId,
            viewId,
            direction,
            group: "primary",
            sort: "name",
            order: "asc",
          }),
        ),
      ),
    ]).then(insert, insert);
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
