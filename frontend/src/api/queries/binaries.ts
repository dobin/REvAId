/**
 * `GET /binaries` and `GET /binaries/{id}/entry-points` (E1, E1b).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type {
  BinaryId,
  BinarySummaryDto,
  EntryPointsDto,
  FunctionSearchPageDto,
  GhidraExportDocument,
  ImportResultDto,
} from "@/api/types";

async function fetchBinaries(): Promise<BinarySummaryDto[]> {
  return apiClient.get<BinarySummaryDto[]>("/binaries");
}

export function useBinariesQuery() {
  return useQuery({
    queryKey: ["binaries"],
    queryFn: fetchBinaries,
  });
}

async function fetchEntryPoints(binaryId: BinaryId): Promise<EntryPointsDto> {
  return apiClient.get<EntryPointsDto>(`/binaries/${String(binaryId)}/entry-points`);
}

export function useEntryPointsQuery(binaryId: BinaryId | null) {
  return useQuery({
    queryKey: ["entry-points", binaryId],
    queryFn: () => fetchEntryPoints(binaryId as BinaryId),
    enabled: binaryId !== null,
  });
}

async function fetchFunctionSearch(
  binaryId: BinaryId,
  query: string,
): Promise<FunctionSearchPageDto> {
  const params = new URLSearchParams({ q: query });
  return apiClient.get<FunctionSearchPageDto>(
    `/binaries/${String(binaryId)}/functions?${params.toString()}`,
  );
}

/**
 * `GET /binaries/{id}/functions?q=...` (B11/E1a) — searches `name_ghidra`,
 * `name_analyst`, `notes`, and `address` for a substring match. Disabled
 * until both a binary is selected and the query is non-empty, so an empty
 * sidebar search box does not fetch the whole (unfiltered) function list.
 */
export function useFunctionSearchQuery(binaryId: BinaryId | null, query: string) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: ["function-search", binaryId, trimmed],
    queryFn: () => fetchFunctionSearch(binaryId as BinaryId, trimmed),
    enabled: binaryId !== null && trimmed.length > 0,
  });
}

/**
 * `DELETE /binaries/{id}?confirm={name}` — the API requires the binary
 * name as a `confirm` query param to guard against accidental deletes.
 * Refreshes the binaries list on success.
 */
export function useDeleteBinaryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: BinaryId; name: string }) =>
      apiClient.delete<void>(`/binaries/${String(id)}`, { confirm: name }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["binaries"] });
    },
  });
}

/**
 * `POST /binaries/import` (I12) — ingest a Ghidra JSON export as a binary.
 * Refreshes the binary picker on success; the caller selects the new binary.
 */
export function useImportBinaryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (document: GhidraExportDocument) =>
      apiClient.post<ImportResultDto>("/binaries/import", document),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["binaries"] });
    },
  });
}
