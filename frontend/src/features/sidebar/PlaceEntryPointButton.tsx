/**
 * Manual stopgap for placing a root node (D8/B10a) on an empty canvas.
 *
 * The real affordance for this — `SearchOmnibox` (name/address search) and
 * the callstack-import dialog — is I11 scope. Until then, an empty view has
 * no way to get its first node onto the canvas at all. This button uses the
 * binary's first entry-point suggestion (E1b, already implemented) and
 * upserts it as a `originKind: "root"` node via the existing batch-patch
 * endpoint (TAD §4.3 #12) — the same call `SearchOmnibox` will eventually
 * make, just without the search UI in front of it.
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
