/**
 * Wipes every node from the view and clears local position state, leaving a
 * blank canvas. Sends `PATCH /views/{id}/nodes` with `remove: [all ids]` so
 * the server is also cleared, then calls `clearPositions` on the canvas slice
 * to drop any pinned/drag positions that would otherwise linger in Zustand.
 *
 * Intentionally does NOT reset the camera — the user can pan/zoom themselves.
 */
import { useViewQuery } from "@/api/queries/views";
import { usePatchViewNodesMutation } from "@/api/queries/viewNodes";
import type { ViewId } from "@/api/types";
import { useAppStore } from "@/store";

export function ResetCanvasButton({ viewId }: { viewId: ViewId }) {
  const view = useViewQuery(viewId);
  const patchNodes = usePatchViewNodesMutation(viewId);
  const clearPositions = useAppStore((s) => s.clearPositions);

  const nodeIds = view.data?.nodes.map((n) => n.functionId) ?? [];
  const hasNodes = nodeIds.length > 0;

  return (
    <button
      type="button"
      disabled={!hasNodes || patchNodes.isPending}
      onClick={() => {
        if (nodeIds.length === 0) return;
        patchNodes.mutate(
          { remove: nodeIds },
          {
            onSuccess: () => {
              clearPositions();
            },
          },
        );
      }}
      style={{
        width: "100%",
        padding: "0.375rem 0.5rem",
        marginBottom: "0.75rem",
        fontSize: "0.8125rem",
        cursor: hasNodes ? "pointer" : "not-allowed",
      }}
      title={hasNodes ? "Remove all nodes and reset the canvas" : "Canvas is already empty"}
    >
      {patchNodes.isPending ? "Clearing…" : "✕ Reset canvas"}
    </button>
  );
}
