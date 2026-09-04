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
import { fetchImportJob, useBinariesQuery, useImportBinaryMutation } from "@/api/queries/binaries";
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
  border: "1px solid #d1d5db",
  background: "#f9fafb",
  cursor: "pointer",
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
  const [document, setDocument] = useState<GhidraExportDocument | null>(null);
  const [duplicateChoice, setDuplicateChoice] = useState<"overwrite" | "new" | null>(null);
  const [newBinaryName, setNewBinaryName] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [isWaitingForImport, setIsWaitingForImport] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const importGeneration = useRef(0);
  const importMutation = useImportBinaryMutation();
  const { data: binaries } = useBinariesQuery();

  const reset = () => {
    importGeneration.current += 1;
    setFileName(null);
    setDocument(null);
    setDuplicateChoice(null);
    setNewBinaryName("");
    setParseError(null);
    setImportError(null);
    setIsWaitingForImport(false);
    importMutation.reset();
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

  const handleImport = () => {
    if (!document) return;
    const binaryName = duplicateChoice === "new" ? newBinaryName.trim() : document.binary.name;
    if (!binaryName) return;
    const importDocument =
      binaryName === document.binary.name
        ? document
        : { ...document, binary: { ...document.binary, name: binaryName } };
    const generation = importGeneration.current;
    setImportError(null);
    importMutation.mutate(importDocument, {
      onSuccess: (accepted) => {
        if (generation !== importGeneration.current) return;
        setIsWaitingForImport(true);
        void (async () => {
          try {
            while (generation === importGeneration.current) {
              const status = await fetchImportJob(accepted.jobId);
              if (generation !== importGeneration.current) return;

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
      },
    });
  };

  const apiErrorMessage =
    importError ??
    (importMutation.error instanceof ApiError
      ? importMutation.error.message
      : importMutation.error
        ? "Import failed."
        : null);

  const existingBinary =
    document && Array.isArray(binaries)
      ? binaries.find(
          (binary) =>
            binary.name === document.binary.name &&
            binary.version === (document.binary.version ?? ""),
        ) ?? null
      : null;
  const needsDuplicateChoice = existingBinary !== null;
  const canImport =
    document &&
    (!needsDuplicateChoice || duplicateChoice !== null) &&
    (duplicateChoice !== "new" || newBinaryName.trim().length > 0) &&
    !importMutation.isPending &&
    !isWaitingForImport;

  return (
    <Dialog
      open={open}
      onOpenChange={handleOpenChange}
      title="Import binary from Ghidra export"
      trigger={
        <button type="button" style={buttonStyle} title="Import a Ghidra JSON export">
          ⬆ (Re) Import binary
        </button>
      }
    >
      <p style={{ margin: "0 0 0.75rem", fontSize: "0.8125rem", color: "#6b7280" }}>
        Select a JSON file produced by <code>GraphRevExport.java</code>. Re-importing the
        same binary updates it without losing your names or notes.
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

      {needsDuplicateChoice && document && !isWaitingForImport && (
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
          <strong>{document.binary.name}</strong> already exists.
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
            <button
              type="button"
              style={primaryButtonStyle}
              aria-pressed={duplicateChoice === "overwrite"}
              onClick={() => setDuplicateChoice("overwrite")}
            >
              Overwrite / refresh
            </button>
            <button
              type="button"
              style={primaryButtonStyle}
              aria-pressed={duplicateChoice === "new"}
              onClick={() => setDuplicateChoice("new")}
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
                onChange={(event) => setNewBinaryName(event.target.value)}
                placeholder={`${document.binary.name} (copy)`}
                style={{ display: "block", width: "100%", boxSizing: "border-box", marginTop: "0.25rem" }}
              />
            </label>
          )}
        </div>
      )}

      {parseError && (
        <p style={{ margin: "0 0 0.75rem", fontSize: "0.8125rem", color: "#b91c1c" }}>
          {parseError}
        </p>
      )}

      {apiErrorMessage && (
        <p style={{ margin: "0 0 0.75rem", fontSize: "0.8125rem", color: "#b91c1c" }}>
          {apiErrorMessage}
        </p>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
        <button
          type="button"
          style={{ ...primaryButtonStyle, background: "#ffffff" }}
          onClick={() => {
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
          {importMutation.isPending || isWaitingForImport ? "Importing…" : "Import"}
        </button>
      </div>
    </Dialog>
  );
}
