/**
 * One-click stopgap for placing a root node (D8/B10a) on an empty canvas.
 *
 * `FunctionSearchInput` now covers the general "find any function by
 * name/address and add it" case (name/address search, I11 scope); this
 * button remains as a zero-typing shortcut that uses the binary's first
 * entry-point suggestion (E1b) and upserts it as an `originKind: "root"`
 * node via the same batch-patch endpoint (TAD §4.3 #12).
 */
import { useEffect, useRef } from "react";
import { useEntryPointsQuery } from "@/api/queries/binaries";
import { usePatchViewMutation, useViewQuery } from "@/api/queries/views";
import { usePatchViewNodesMutation } from "@/api/queries/viewNodes";
import type { BinaryId, ViewId } from "@/api/types";

/** Places the binary's preferred entry point as this view's root node. */
export function usePlaceEntryPoint(binaryId: BinaryId, viewId: ViewId) {
  const entryPoints = useEntryPointsQuery(binaryId);
  const patchNodes = usePatchViewNodesMutation(viewId);
  const patchView = usePatchViewMutation(viewId);
  const topEntryPoint = entryPoints.data?.entryPoints[0];

  const placeEntryPoint = async (): Promise<void> => {
    if (!topEntryPoint) return;
    await patchNodes.mutateAsync({
      upsert: [{ functionId: topEntryPoint.id, visible: true, originKind: "root" }],
    });
    await patchView.mutateAsync({ rootFunctionId: topEntryPoint.id });
  };

  return {
    topEntryPoint,
    placeEntryPoint,
    isPending: entryPoints.isPending || patchNodes.isPending || patchView.isPending,
    isEntryPointsError: entryPoints.isError,
  };
}

export function PlaceEntryPointButton({
  binaryId,
  viewId,
}: {
  binaryId: BinaryId;
  viewId: ViewId;
}) {
  const { topEntryPoint, placeEntryPoint, isPending } = usePlaceEntryPoint(binaryId, viewId);

  return (
    <button
      type="button"
      disabled={!topEntryPoint || isPending}
      onClick={() => {
        void placeEntryPoint();
      }}
      style={{
        display: "block",
        padding: "0.125rem 0",
        marginBottom: "0.25rem",
        fontSize: "0.8125rem",
        textAlign: "left",
        background: "none",
        border: "none",
        cursor: topEntryPoint ? "pointer" : "not-allowed",
      }}
      title={
        topEntryPoint
          ? `Place entry-point on the canvas`
          : "No entry-point suggestions for this binary"
      }
    >
      {isPending
        ? "Placing…"
        : `+ Place entry point`}
    </button>
  );
}

/**
 * Adds the preferred entry point when a view is first loaded empty. Later
 * transitions to empty (notably Reset canvas) are intentionally ignored:
 * that action explicitly performs its remove-then-add sequence instead.
 */
export function AutoPlaceEntryPoint({ binaryId, viewId }: { binaryId: BinaryId; viewId: ViewId }) {
  const view = useViewQuery(viewId);
  const { topEntryPoint, placeEntryPoint, isPending, isEntryPointsError } = usePlaceEntryPoint(
    binaryId,
    viewId,
  );
  const handledInitialView = useRef(false);

  useEffect(() => {
    if (!view.data || handledInitialView.current) return;
    if (view.data.nodes.length > 0) {
      handledInitialView.current = true;
      return;
    }
    if (isPending) return;
    // There is nothing to place for a binary without entry-point candidates.
    if (!topEntryPoint || isEntryPointsError) {
      handledInitialView.current = true;
      return;
    }
    // Set this before starting the mutation so Strict Mode/effect re-runs
    // cannot submit the same root twice.
    handledInitialView.current = true;
    void placeEntryPoint();
  }, [view.data, topEntryPoint, placeEntryPoint, isPending, isEntryPointsError]);

  return null;
}
