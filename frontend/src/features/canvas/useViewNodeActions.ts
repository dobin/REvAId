/**
 * Small per-field wrappers around `usePatchViewNodesMutation` (I6) — hide
 * (✕, D13's `visible:false`), colour swatches (D16), and collapse
 * (`CollapsedChip`, D14) all patch exactly one field on one node.
 */
import { useQueryClient } from "@tanstack/react-query";
import { usePatchViewNodesMutation } from "@/api/queries/viewNodes";
import type { FunctionId, NodeColor, ViewDto, ViewId } from "@/api/types";

/**
 * Transitive callees of `functionId` in the view's provenance forest: every
 * node whose `originFunctionId` chain leads back to it, EXCLUDING `fanin`
 * nodes (those are *callers* fanned out from the card, not its children).
 * Pure function over the node list so it's trivially testable.
 */
export function descendantCallees(nodes: ViewDto["nodes"], functionId: FunctionId): Set<FunctionId> {
  // children(x) = nodes spawned from x that are NOT fanin callers of x.
  const childrenOf = new Map<FunctionId, FunctionId[]>();
  for (const node of nodes) {
    if (node.originFunctionId === null) continue;
    if (node.originKind === "fanin") continue;
    const list = childrenOf.get(node.originFunctionId);
    if (list) list.push(node.functionId);
    else childrenOf.set(node.originFunctionId, [node.functionId]);
  }

  const descendants = new Set<FunctionId>();
  const queue = [functionId];
  while (queue.length > 0) {
    const current = queue.pop() as FunctionId;
    for (const child of childrenOf.get(current) ?? []) {
      if (descendants.has(child)) continue;
      descendants.add(child);
      queue.push(child);
    }
  }
  return descendants;
}

export function useViewNodeActions(viewId: ViewId) {
  const patchNodes = usePatchViewNodesMutation(viewId);
  const queryClient = useQueryClient();

  return {
    setVisible: (functionId: FunctionId, visible: boolean) => {
      // Hiding a card orphans its callees (their connector edges vanish with
      // the parent, D8b), so hide the whole provenance subtree with it.
      // Re-showing only restores the card itself — the user can re-fan-out.
      let upsert: { functionId: FunctionId; visible: boolean }[] = [
        { functionId, visible },
      ];
      if (!visible) {
        const view = queryClient.getQueryData<ViewDto>(["view", viewId]);
        if (view) {
          upsert = upsert.concat(
            [...descendantCallees(view.nodes, functionId)].map((id) => ({
              functionId: id,
              visible: false,
            })),
          );
        }
      }
      patchNodes.mutate({ upsert });
    },
    setColor: (functionId: FunctionId, color: NodeColor | null) => {
      patchNodes.mutate({ upsert: [{ functionId, color }] });
    },
    setCollapsed: (functionId: FunctionId, collapsed: boolean) => {
      patchNodes.mutate({ upsert: [{ functionId, collapsed }] });
    },
  };
}
