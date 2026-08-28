/**
 * Wipes every node from the view, clears local position state, then replaces
 * the binary's preferred entry point as the new root. It sends separate
 * remove and upsert requests because the server applies an upsert before a
 * remove in a combined request.
 *
 * Intentionally does NOT reset the camera — the user can pan/zoom themselves.
 */
import { usePlaceEntryPoint } from "./PlaceEntryPointButton";
import { useViewQuery } from "@/api/queries/views";
import { usePatchViewNodesMutation } from "@/api/queries/viewNodes";
import type { BinaryId, ViewId } from "@/api/types";
import { useAppStore } from "@/store";

export function ResetCanvasButton({ binaryId, viewId }: { binaryId: BinaryId; viewId: ViewId }) {
  const view = useViewQuery(viewId);
  const patchNodes = usePatchViewNodesMutation(viewId);
  const { topEntryPoint, placeEntryPoint, isPending: isPlacingEntryPoint } = usePlaceEntryPoint(
    binaryId,
    viewId,
  );
  const clearPositions = useAppStore((s) => s.clearPositions);

  const nodeIds = view.data?.nodes.map((n) => n.functionId) ?? [];
  const hasNodes = nodeIds.length > 0;

  return (
    <button
      type="button"
      disabled={!hasNodes || !topEntryPoint || patchNodes.isPending || isPlacingEntryPoint}
      onClick={() => {
        if (nodeIds.length === 0 || !topEntryPoint) return;
        void patchNodes.mutateAsync({ remove: nodeIds }).then(async () => {
          clearPositions();
          await placeEntryPoint();
        });
      }}
      style={{
        display: "block",
        padding: "0.125rem 0",
        marginBottom: "0.25rem",
        fontSize: "0.8125rem",
        textAlign: "left",
        background: "none",
        border: "none",
        cursor: hasNodes && topEntryPoint ? "pointer" : "not-allowed",
      }}
      title={
        !hasNodes
          ? "Canvas is already empty"
          : !topEntryPoint
            ? "No entry-point suggestions for this binary"
            : "Remove all nodes and place the entry point"
      }
    >
      {patchNodes.isPending ? "Clearing…" : isPlacingEntryPoint ? "Placing…" : "✕ Reset canvas"}
    </button>
  );
}
