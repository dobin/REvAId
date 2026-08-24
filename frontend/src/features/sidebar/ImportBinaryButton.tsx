/**
 * Sidebar action: import a binary from a Ghidra JSON export (I12).
 *
 * Opens a dialog with a file picker, parses the file client-side, POSTs the
 * parsed document to `POST /binaries/import`, and on success selects the new
 * binary via `onImported`. Feedback is inline (no toast system exists yet).
 */
import { useRef, useState } from "react";
import { ApiError } from "@/api/client";
import { useImportBinaryMutation } from "@/api/queries/binaries";
import type { BinaryId, GhidraExportDocument, ImportResultDto } from "@/api/types";
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
  const [open, setOpen] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [document, setDocument] = useState<GhidraExportDocument | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const importMutation = useImportBinaryMutation();

  const reset = () => {
    setFileName(null);
    setDocument(null);
    setParseError(null);
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
    importMutation.mutate(document, {
      onSuccess: (result: ImportResultDto) => {
        handleOpenChange(false);
        onImported(result.binaryId);
      },
    });
  };

  const apiErrorMessage =
    importMutation.error instanceof ApiError
      ? importMutation.error.message
      : importMutation.error
        ? "Import failed."
        : null;

  return (
    <Dialog
      open={open}
      onOpenChange={handleOpenChange}
      title="Import binary from Ghidra export"
      trigger={
        <button type="button" style={buttonStyle} title="Import a Ghidra JSON export">
          ⬆ Import binary…
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
            cursor: document && !importMutation.isPending ? "pointer" : "not-allowed",
            opacity: document && !importMutation.isPending ? 1 : 0.6,
          }}
          disabled={!document || importMutation.isPending}
          onClick={handleImport}
        >
          {importMutation.isPending ? "Importing…" : "Import"}
        </button>
      </div>
    </Dialog>
  );
}
