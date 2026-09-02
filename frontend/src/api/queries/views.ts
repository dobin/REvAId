/**
 * View queries + mutations (TAD §4.2 #9-#11, I6). `useViewsQuery` was pulled
 * forward to I5 as a narrow listing; everything else here is I6 scope.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type {
  BinaryId,
  SetLastViewRequest,
  ViewCreateRequest,
  ViewDto,
  ViewId,
  ViewPatchRequest,
  ViewSummaryDto,
} from "@/api/types";

async function fetchViews(binaryId: BinaryId): Promise<ViewSummaryDto[]> {
  return apiClient.get<ViewSummaryDto[]>(`/binaries/${String(binaryId)}/views`);
}

export function useViewsQuery(
  binaryId: BinaryId | null,
  opts?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ["views", binaryId],
    queryFn: () => fetchViews(binaryId as BinaryId),
    // ADR 0006: in public mode the listing endpoint is closed (403), so
    // callers disable this query rather than fetch a forbidden listing.
    enabled: binaryId !== null && (opts?.enabled ?? true),
  });
}

async function fetchView(viewId: ViewId): Promise<ViewDto> {
  return apiClient.get<ViewDto>(`/views/${String(viewId)}`);
}

/** `GET /views/{id}` — the full record with `camera`/`nodes[]` (I6). */
export function useViewQuery(viewId: ViewId | null) {
  return useQuery({
    queryKey: ["view", viewId],
    queryFn: () => fetchView(viewId as ViewId),
    enabled: viewId !== null,
  });
}

export function useCreateViewMutation(binaryId: BinaryId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: ViewCreateRequest) =>
      apiClient.post<ViewDto>(`/binaries/${String(binaryId)}/views`, request),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["views", binaryId] });
    },
  });
}

export function usePatchViewMutation(viewId: ViewId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: ViewPatchRequest) =>
      apiClient.patch<ViewDto>(`/views/${String(viewId)}`, request),
    onSuccess: (updated) => {
      queryClient.setQueryData(["view", viewId], updated);
    },
  });
}

export function useDuplicateViewMutation(binaryId: BinaryId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (viewId: ViewId) => apiClient.post<ViewDto>(`/views/${String(viewId)}/duplicate`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["views", binaryId] });
    },
  });
}

export function useDeleteViewMutation(binaryId: BinaryId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (viewId: ViewId) => apiClient.delete<undefined>(`/views/${String(viewId)}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["views", binaryId] });
    },
  });
}

export function useSetLastViewMutation(binaryId: BinaryId) {
  return useMutation({
    mutationFn: (request: SetLastViewRequest) =>
      apiClient.post<undefined>(`/binaries/${String(binaryId)}/last-view`, request),
  });
}
