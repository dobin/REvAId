/**
 * One-click stopgap for placing a root node (D8/B10a) on an empty canvas.
 *
 * `FunctionSearchInput` now covers the general "find any function by
 * name/address and add it" case (name/address search, I11 scope); this
 * button remains as a zero-typing shortcut that uses the binary's first
 * entry-point suggestion (E1b) and upserts it as an `originKind: "root"`
 * node via the same batch-patch endpoint (TAD §4.3 #12).
 */
import { useEntryPointsQuery } from "@/api/queries/binaries";
import { usePatchViewNodesMutation } from "@/api/queries/viewNodes";
import type { BinaryId, ViewId } from "@/api/types";

export function PlaceEntryPointButton({
  binaryId,
  viewId,
}: {
  binaryId: BinaryId;
  viewId: ViewId;
}) {
  const entryPoints = useEntryPointsQuery(binaryId);
  const patchNodes = usePatchViewNodesMutation(viewId);

  const topEntryPoint = entryPoints.data?.entryPoints[0];

  return (
    <button
      type="button"
      disabled={!topEntryPoint || patchNodes.isPending}
      onClick={() => {
        if (!topEntryPoint) return;
        patchNodes.mutate({
          upsert: [{ functionId: topEntryPoint.id, visible: true, originKind: "root" }],
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
        cursor: topEntryPoint ? "pointer" : "not-allowed",
      }}
      title={
        topEntryPoint
          ? `Place ${topEntryPoint.displayName} on the canvas`
          : "No entry-point suggestions for this binary"
      }
    >
      {patchNodes.isPending
        ? "Placing…"
        : `+ Place ${topEntryPoint ? topEntryPoint.displayName : "entry point"}`}
    </button>
  );
}
