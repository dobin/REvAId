/**
 * Unpins every node in the view so the ELK layout algorithm re-positions them
 * all from scratch, discarding any manual drag moves the user made (D15's
 * "pinned" flag is what keeps a node fixed; clearing it hands all positions
 * back to ELK).
 *
 * Flow:
 *  1. Read the current node list from the view cache.
 *  2. PATCH the server with `pinned: false` for every node so the cleared
 *     state survives a page reload.
 *  3. On success, call `unpinAll` on the canvas slice — this clears the
 *     local Zustand pin flags, which causes `CanvasView`'s `layoutKey`
 *     effect to include all nodes as ELK participants again, triggering a
 *     fresh full layout.
 */
import { useViewQuery } from "@/api/queries/views";
import { usePatchViewNodesMutation } from "@/api/queries/viewNodes";
import type { ViewId } from "@/api/types";
import { useAppStore } from "@/store";

export function RebalanceButton({ viewId }: { viewId: ViewId }) {
  const view = useViewQuery(viewId);
  const patchNodes = usePatchViewNodesMutation(viewId);
  const unpinAll = useAppStore((s) => s.unpinAll);

  const pinnedNodes = view.data?.nodes.filter((n) => n.pinned) ?? [];
  const hasPinned = pinnedNodes.length > 0;

  return (
    <button
      type="button"
      disabled={!hasPinned || patchNodes.isPending}
      onClick={() => {
        if (pinnedNodes.length === 0) return;
        patchNodes.mutate(
          {
            upsert: pinnedNodes.map((n) => ({
              functionId: n.functionId,
              pinned: false,
            })),
          },
          {
            onSuccess: () => {
              unpinAll();
            },
          },
        );
      }}
      style={{
        width: "100%",
        padding: "0.375rem 0.5rem",
        marginBottom: "0.75rem",
        fontSize: "0.8125rem",
        cursor: hasPinned ? "pointer" : "not-allowed",
      }}
      title={
        hasPinned
          ? "Re-run the layout algorithm, discarding all manual moves"
          : "No manually moved nodes to rebalance"
      }
    >
      {patchNodes.isPending ? "Rebalancing…" : "⟳ Rebalance layout"}
    </button>
  );
}
