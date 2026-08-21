/**
 * Small per-field wrappers around `usePatchViewNodesMutation` (I6) — hide
 * (✕, D13's `visible:false`), colour swatches (D16), and collapse
 * (`CollapsedChip`, D14) all patch exactly one field on one node.
 */
import { usePatchViewNodesMutation } from "@/api/queries/viewNodes";
import type { FunctionId, NodeColor, ViewId } from "@/api/types";

export function useViewNodeActions(viewId: ViewId) {
  const patchNodes = usePatchViewNodesMutation(viewId);

  return {
    setVisible: (functionId: FunctionId, visible: boolean) => {
      patchNodes.mutate({ upsert: [{ functionId, visible }] });
    },
    setColor: (functionId: FunctionId, color: NodeColor | null) => {
      patchNodes.mutate({ upsert: [{ functionId, color }] });
    },
    setCollapsed: (functionId: FunctionId, collapsed: boolean) => {
      patchNodes.mutate({ upsert: [{ functionId, collapsed }] });
    },
  };
}
