/**
 * `GET /functions/{id}/neighbours` (E2, E2a, E2b) — the card's tables.
 * Side-effect free by construction (C2c) — this is a plain GET, no
 * summary-demand wiring in I5 (that arrives with I9).
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { FunctionId, NeighbourPageDto, ViewId } from "@/api/types";

export interface NeighbourQueryParams {
  functionId: FunctionId;
  viewId: ViewId;
  direction: "callees" | "callers";
  group?: "primary" | "utility";
  limit?: number;
  offset?: number;
  sort?: "name" | "address" | "fanIn";
  order?: "asc" | "desc";
  filter?: string;
}

async function fetchNeighbours(params: NeighbourQueryParams): Promise<NeighbourPageDto> {
  const query = new URLSearchParams();
  query.set("viewId", String(params.viewId));
  query.set("direction", params.direction);
  if (params.group) query.set("group", params.group);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  if (params.sort) query.set("sort", params.sort);
  if (params.order) query.set("order", params.order);
  if (params.filter) query.set("filter", params.filter);

  return apiClient.get<NeighbourPageDto>(
    `/functions/${String(params.functionId)}/neighbours?${query.toString()}`,
  );
}

/**
 * Query key includes every param that affects the response so that changing
 * `filter`/`sort`/`order`/`group`/`offset` triggers a real refetch rather
 * than serving a stale cached page.
 */
export function useNeighboursQuery(params: NeighbourQueryParams) {
  return useQuery({
    queryKey: [
      "neighbours",
      params.functionId,
      params.viewId,
      params.direction,
      params.group ?? "primary",
      params.limit,
      params.offset,
      params.sort,
      params.order,
      params.filter,
    ],
    queryFn: () => fetchNeighbours(params),
  });
}
