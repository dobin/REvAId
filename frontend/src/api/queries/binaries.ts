/**
 * `GET /binaries` and `GET /binaries/{id}/entry-points` (E1, E1b).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type {
  BinaryId,
  BinarySummaryDto,
  EntryPointsDto,
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
