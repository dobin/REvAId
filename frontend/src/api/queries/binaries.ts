/**
 * `GET /binaries` and `GET /binaries/{id}/entry-points` (E1, E1b).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type {
  BinaryId,
  BinarySummaryDto,
  EntryPointsDto,
  FunctionDto,
  FunctionSearchPageDto,
  GhidraExportDocument,
  ImportJobAcceptedDto,
  ImportJobStatusDto,
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

async function fetchFunctionByAddress(binaryId: BinaryId, address: number): Promise<FunctionDto> {
  const params = new URLSearchParams({ address: `0x${address.toString(16)}` });
  return apiClient.get<FunctionDto>(
    `/binaries/${String(binaryId)}/functions/by-address?${params.toString()}`,
  );
}

/** Resolve a canonical Ghidra static address to its nearest known function. */
export function useFunctionAddressQuery(binaryId: BinaryId | null, address: number | null) {
  return useQuery({
    queryKey: ["function-address", binaryId, address],
    queryFn: () => fetchFunctionByAddress(binaryId as BinaryId, address as number),
    enabled: binaryId !== null && address !== null,
    retry: false,
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
      apiClient.delete<undefined>(`/binaries/${String(id)}`, { confirm: name }),
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
  return useMutation({
    mutationFn: (document: GhidraExportDocument) =>
      apiClient.post<ImportJobAcceptedDto>("/binaries/import", document),
  });
}

/** Upload a raw executable for local decompilation before normal ingestion. */
export function useDecompileBinaryMutation() {
  return useMutation({
    mutationFn: ({ file, name, version }: { file: File; name: string; version: string }) => {
      const params = new URLSearchParams({ name, version });
      return apiClient.postBinary<ImportJobAcceptedDto>(`/binaries/decompile?${params.toString()}`, file);
    },
  });
}

/** Read the progress and final outcome of an asynchronous binary import. */
export function fetchImportJob(jobId: string): Promise<ImportJobStatusDto> {
  return apiClient.get<ImportJobStatusDto>(`/binaries/imports/${encodeURIComponent(jobId)}`);
}

export function cancelImportJob(jobId: string): Promise<ImportJobStatusDto> {
  return apiClient.delete<ImportJobStatusDto>(`/binaries/imports/${encodeURIComponent(jobId)}`);
}
