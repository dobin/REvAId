/**
 * `GET /binaries/{id}/views` — minimal read-only listing (I5, pulled
 * forward from I6) used only to resolve a `viewId` for the neighbours
 * endpoint.
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { BinaryId, ViewSummaryDto } from "@/api/types";

async function fetchViews(binaryId: BinaryId): Promise<ViewSummaryDto[]> {
  return apiClient.get<ViewSummaryDto[]>(`/binaries/${String(binaryId)}/views`);
}

export function useViewsQuery(binaryId: BinaryId | null) {
  return useQuery({
    queryKey: ["views", binaryId],
    queryFn: () => fetchViews(binaryId as BinaryId),
    enabled: binaryId !== null,
  });
}
