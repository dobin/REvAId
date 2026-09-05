/**
 * Sidebar action: import a binary from a Ghidra JSON export (I12).
 *
 * Opens a dialog with a file picker, parses the file client-side, POSTs the
 * parsed document to `POST /binaries/import`, and on success selects the new
 * binary via `onImported`. Feedback is inline (no toast system exists yet).
 */
import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import {
  cancelImportJob,
  fetchImportJob,
  useBinariesQuery,
  useDecompileBinaryMutation,
  useImportBinaryMutation,
} from "@/api/queries/binaries";
import type { BinaryId, GhidraExportDocument } from "@/api/types";
import { Dialog } from "@/components/Dialog";

const buttonStyle: React.CSSProperties = {
  display: "block",
  padding: "0.125rem 0",
  marginBottom: "0.25rem",
  fontSize: "0.8125rem",
  textAlign: "left",
  background: "none",
  border: "none",
  cursor: "pointer",
};

const primaryButtonStyle: React.CSSProperties = {
  padding: "0.375rem 0.75rem",
  fontSize: "0.8125rem",
  borderRadius: "0.375rem",
  borderWidth: "1px",
  borderStyle: "solid",
  borderColor: "#d1d5db",
  background: "#f9fafb",
  cursor: "pointer",
};

const selectedSourceTabStyle: React.CSSProperties = {
  ...primaryButtonStyle,
  borderColor: "#2563eb",
  background: "#dbeafe",
  color: "#1d4ed8",
  fontWeight: 600,
};

const importPollIntervalMs = 500;

function parseExport(text: string): GhidraExportDocument {
  const parsed = JSON.parse(text) as unknown;
  if (
    typeof parsed !== "object" ||
    parsed === null ||
    !("schemaVersion" in parsed) ||
    !("binary" in parsed)
  ) {
    throw new Error("Not a Ghidra export: missing 'schemaVersion' or 'binary'.");
  }
  return parsed as GhidraExportDocument;
}

export function ImportBinaryButton({
  onImported,
}: {
  onImported: (binaryId: BinaryId) => void;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [sourceKind, setSourceKind] = useState<"json" | "binary">("binary");
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [phase, setPhase] = useState<string | null>(null);
  const [document, setDocument] = useState<GhidraExportDocument | null>(null);
  const [duplicateChoice, setDuplicateChoice] = useState<"overwrite" | "new" | null>(null);
  const [newBinaryName, setNewBinaryName] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [isWaitingForImport, setIsWaitingForImport] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const importGeneration = useRef(0);
  const importMutation = useImportBinaryMutation();
  const decompileMutation = useDecompileBinaryMutation();
  const { data: binaries } = useBinariesQuery();

  const reset = () => {
    importGeneration.current += 1;
    setFileName(null);
    setRawFile(null);
    setJobId(null);
    setPhase(null);
    setDocument(null);
    setDuplicateChoice(null);
    setNewBinaryName("");
    setParseError(null);
    setImportError(null);
    setIsWaitingForImport(false);
    importMutation.reset();
    decompileMutation.reset();
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) reset();
  };

  const handleFile = async (file: File) => {
    setParseError(null);
    setDocument(null);
    setDuplicateChoice(null);
    setNewBinaryName("");
    setFileName(file.name);
    try {
      const text = await file.text();
      setDocument(parseExport(text));
    } catch (err) {
      setDocument(null);
      setParseError(err instanceof Error ? err.message : "Could not read the file.");
    }
  };

  const handleRawFile = (file: File) => {
    setParseError(null);
    setRawFile(file);
    setFileName(file.name);
    setDuplicateChoice(null);
    setNewBinaryName("");
  };

  const waitForImport = (accepted: { jobId: string }) => {
    setJobId(accepted.jobId);
    const generation = importGeneration.current;
    setImportError(null);
    setIsWaitingForImport(true);
    void (async () => {
          try {
            while (generation === importGeneration.current) {
              const status = await fetchImportJob(accepted.jobId);
              if (generation !== importGeneration.current) return;
              setPhase(status.phase);

              if (status.phase === "completed" && status.result !== null) {
                await queryClient.invalidateQueries({ queryKey: ["binaries"] });
                if (generation !== importGeneration.current) return;
                handleOpenChange(false);
                onImported(status.result.binaryId);
                return;
              }
              if (status.phase === "failed" || status.phase === "cancelled") {
                setImportError(
                  status.errorMessage ??
                    (status.phase === "cancelled" ? "Import was cancelled." : "Import failed."),
                );
                setIsWaitingForImport(false);
                return;
              }

              await new Promise<void>((resolve) => {
                window.setTimeout(resolve, importPollIntervalMs);
              });
            }
          } catch (err) {
            if (generation !== importGeneration.current) return;
            setImportError(err instanceof Error ? err.message : "Could not check import progress.");
            setIsWaitingForImport(false);
          }
    })();
  };

  const handleImport = () => {
    if (sourceKind === "binary") {
      if (!rawFile) return;
      const binaryName = duplicateChoice === "new" ? newBinaryName.trim() : rawFile.name;
      if (!binaryName) return;
      decompileMutation.mutate(
        { file: rawFile, name: binaryName, version: "" },
        { onSuccess: waitForImport },
      );
      return;
    }
    if (!document) return;
    const binaryName = duplicateChoice === "new" ? newBinaryName.trim() : document.binary.name;
    if (!binaryName) return;
    const importDocument =
      binaryName === document.binary.name
        ? document
        : { ...document, binary: { ...document.binary, name: binaryName } };
    importMutation.mutate(importDocument, { onSuccess: waitForImport });
  };

  const apiErrorMessage =
    importError ??
    (importMutation.error instanceof ApiError
      ? importMutation.error.message
      : importMutation.error
        ? "Import failed."
        : decompileMutation.error instanceof ApiError
          ? decompileMutation.error.message
          : decompileMutation.error
            ? "Analysis upload failed."
            : null);

  const selectedBinaryName = sourceKind === "json" ? document?.binary.name : rawFile?.name;
  const selectedBinaryVersion = sourceKind === "json" ? (document?.binary.version ?? "") : "";
  const existingBinary =
    selectedBinaryName && Array.isArray(binaries)
      ? binaries.find(
          (binary) =>
            binary.name === selectedBinaryName && binary.version === selectedBinaryVersion,
        ) ?? null
      : null;
  const needsDuplicateChoice = existingBinary !== null;
  const canImport =
    (sourceKind === "binary"
      ? rawFile !== null &&
        (!needsDuplicateChoice || duplicateChoice !== null) &&
        (duplicateChoice !== "new" || newBinaryName.trim().length > 0)
      : document &&
        (!needsDuplicateChoice || duplicateChoice !== null) &&
        (duplicateChoice !== "new" || newBinaryName.trim().length > 0)) &&
    !importMutation.isPending && !decompileMutation.isPending &&
    !isWaitingForImport;

  return (
    <Dialog
      open={open}
      onOpenChange={handleOpenChange}
      title="Import or analyze binary"
      trigger={
        <button type="button" style={buttonStyle} title="Import a JSON export or analyze a raw binary">
          ⬆ (Re) Import binary
        </button>
      }
    >
      <div role="tablist" aria-label="Import source" style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <button
          id="raw-binary-tab"
          type="button"
          role="tab"
          aria-selected={sourceKind === "binary"}
          aria-controls="binary-import-source"
          style={sourceKind === "binary" ? selectedSourceTabStyle : primaryButtonStyle}
          onClick={() => { setSourceKind("binary"); }}
        >
          Raw binary
        </button>
        <button
          id="decompiler-export-tab"
          type="button"
          role="tab"
          aria-selected={sourceKind === "json"}
          aria-controls="binary-import-source"
          style={sourceKind === "json" ? selectedSourceTabStyle : primaryButtonStyle}
          onClick={() => { setSourceKind("json"); }}
        >
          .json Export
        </button>
      </div>

      <div
        id="binary-import-source"
        role="tabpanel"
        aria-labelledby={sourceKind === "binary" ? "raw-binary-tab" : "decompiler-export-tab"}
      >
      {sourceKind === "json" ? <>
      <p style={{ margin: "0 0 0.75rem", fontSize: "0.8125rem", color: "#6b7280" }}>
        Select a JSON file produced by <code>GraphRevExport.java</code>. Re-importing the same binary updates it without losing your names or notes.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void handleFile(file);
        }}
        style={{ fontSize: "0.8125rem", marginBottom: "0.75rem" }}
      />

      {fileName && !parseError && document && (
        <p style={{ margin: "0 0 0.75rem", fontSize: "0.8125rem" }}>
          Ready to import <strong>{document.binary.name}</strong> ({document.functions.length}{" "}
          functions, {document.edges.length} edges).
        </p>
      )}

      </> : <>
        <p style={{ margin: "0 0 0.75rem", fontSize: "0.8125rem", color: "#6b7280" }}>
          Upload a binary for analysis by the configured local <code>kuna</code> decompiler.
        </p>
        <input ref={inputRef} type="file" onChange={(event) => { const file = event.target.files?.[0]; if (file) handleRawFile(file); }} style={{ fontSize: "0.8125rem", marginBottom: "0.75rem" }} />
        {rawFile && <p style={{ margin: "0 0 0.75rem", fontSize: "0.8125rem" }}>Ready to analyze <strong>{rawFile.name}</strong> ({Math.ceil(rawFile.size / 1024)} KiB).</p>}
      </>}
      </div>

      {needsDuplicateChoice && selectedBinaryName && !isWaitingForImport && (
        <div
          role="alert"
          style={{
            margin: "0 0 0.75rem",
            padding: "0.625rem",
            border: "1px solid #fbbf24",
            borderRadius: "0.375rem",
            background: "#fffbeb",
            fontSize: "0.8125rem",
          }}
        >
          <strong>{selectedBinaryName}</strong> already exists.
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
            <button
              type="button"
              style={primaryButtonStyle}
              aria-pressed={duplicateChoice === "overwrite"}
              onClick={() => { setDuplicateChoice("overwrite"); }}
            >
              Overwrite / refresh
            </button>
            <button
              type="button"
              style={primaryButtonStyle}
              aria-pressed={duplicateChoice === "new"}
              onClick={() => { setDuplicateChoice("new"); }}
            >
              Open as new binary
            </button>
          </div>
          {duplicateChoice === "new" && (
            <label style={{ display: "block", marginTop: "0.5rem" }}>
              New name
              <input
                type="text"
                value={newBinaryName}
                onChange={(event) => { setNewBinaryName(event.target.value); }}
                placeholder={`${selectedBinaryName} (copy)`}
                style={{ display: "block", width: "100%", boxSizing: "border-box", marginTop: "0.25rem" }}
              />
            </label>
          )}
        </div>
      )}

      {parseError && (
        <p role="alert" style={{ margin: "0 0 0.75rem", fontSize: "0.8125rem", color: "#b91c1c" }}>
          {parseError}
        </p>
      )}

      {apiErrorMessage && (
        <p role="alert" style={{ margin: "0 0 0.75rem", fontSize: "0.8125rem", color: "#b91c1c" }}>
          {apiErrorMessage}
        </p>
      )}

      {isWaitingForImport && <p aria-live="polite" style={{ margin: "0 0 0.75rem", fontSize: "0.8125rem", color: "#6b7280" }}>{phase === "decompiling" ? "Decompiling binary…" : phase === "importing" ? "Importing analysis…" : "Queued for import…"}</p>}

      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
        <button
          type="button"
          style={{ ...primaryButtonStyle, background: "#ffffff" }}
          onClick={() => {
            if (jobId && phase === "decompiling") void cancelImportJob(jobId);
            handleOpenChange(false);
          }}
        >
          Cancel
        </button>
        <button
          type="button"
          style={{
            ...primaryButtonStyle,
            cursor: canImport ? "pointer" : "not-allowed",
            opacity: canImport ? 1 : 0.6,
          }}
          disabled={!canImport}
          onClick={handleImport}
        >
          {importMutation.isPending || decompileMutation.isPending || isWaitingForImport ? "Working…" : sourceKind === "binary" ? "Analyze binary" : "Import"}
        </button>
      </div>
    </Dialog>
  );
}
