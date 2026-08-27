/**
 * `PATCH /views/{id}/nodes` (TAD §4.3 #12, I6). On success, patches the
 * cached `['view', viewId]` entry with the full post-state the backend
 * returns, rather than invalidating + refetching — matches the backend's
 * "so the client can reconcile" contract and avoids an extra round trip.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { ViewDto, ViewId, ViewNodesPatchRequest, ViewNodesPatchResponse } from "@/api/types";

async function patchViewNodes(
  viewId: ViewId,
  request: ViewNodesPatchRequest,
): Promise<ViewNodesPatchResponse> {
  return apiClient.patch<ViewNodesPatchResponse>(`/views/${String(viewId)}/nodes`, request);
}

export function usePatchViewNodesMutation(viewId: ViewId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: ViewNodesPatchRequest) => patchViewNodes(viewId, request),
    onSuccess: (response) => {
      queryClient.setQueryData<ViewDto>(["view", viewId], (view) =>
        view ? { ...view, nodes: response.nodes } : view,
      );
      // Invalidate neighbours queries for this view so that `onCanvas` flags
      // reflect the updated node list without requiring a page reload.
      void queryClient.invalidateQueries({ queryKey: ["neighbours"] });
      void queryClient.invalidateQueries({ queryKey: ["neighbours-infinite"] });
    },
  });
}
