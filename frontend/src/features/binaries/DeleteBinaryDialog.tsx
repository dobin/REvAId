/**
 * Typed-name confirm dialog for `DELETE /binaries/{id}?confirm={name}`.
 * The Delete button stays disabled until the typed name matches exactly.
 */
import { useEffect, useState } from "react";
import { ApiError } from "@/api/client";
import { useDeleteBinaryMutation } from "@/api/queries/binaries";
import type { BinarySummaryDto } from "@/api/types";
import { Dialog } from "@/components/Dialog";

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "0.375rem 0.5rem",
  fontFamily: "var(--gr-font-mono, monospace)",
  fontSize: "0.875rem",
  border: "1px solid #d1d5db",
  borderRadius: "0.375rem",
};

const primaryButtonStyle: React.CSSProperties = {
  padding: "0.375rem 0.75rem",
  fontSize: "0.8125rem",
  borderRadius: "0.375rem",
  border: "1px solid #d1d5db",
  background: "#f9fafb",
  cursor: "pointer",
};

const dangerButtonStyle: React.CSSProperties = {
  ...primaryButtonStyle,
  color: "#b91c1c",
  borderColor: "#fca5a5",
  background: "#fef2f2",
};

export function DeleteBinaryDialog({
  binary,
  open,
  onOpenChange,
}: {
  binary: BinarySummaryDto;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [typedName, setTypedName] = useState("");
  const deleteMutation = useDeleteBinaryMutation();

  // Reset the typed name and any prior error whenever the dialog reopens.
  useEffect(() => {
    if (open) {
      setTypedName("");
      deleteMutation.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, binary.id]);

  const handleDelete = () => {
    deleteMutation.mutate(
      { id: binary.id, name: binary.name },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  };

  const apiErrorMessage =
    deleteMutation.error instanceof ApiError
      ? deleteMutation.error.message
      : deleteMutation.error
        ? "Delete failed."
        : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={`Delete ${binary.name}?`}>
      <p style={{ margin: "0 0 0.75rem", fontSize: "0.875rem" }}>
        This permanently removes the binary, its functions, edges, and views. Type the
        binary name to confirm:
      </p>
      <input
        aria-label="Binary name confirmation"
        style={inputStyle}
        value={typedName}
        onChange={(e) => { setTypedName(e.target.value); }}
        placeholder={binary.name}
        autoComplete="off"
      />
      {apiErrorMessage !== null && (
        <p style={{ margin: "0.5rem 0 0", fontSize: "0.8125rem", color: "#b91c1c" }}>
          {apiErrorMessage}
        </p>
      )}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1rem" }}>
        <button type="button" style={primaryButtonStyle} onClick={() => { onOpenChange(false); }}>
          Cancel
        </button>
        <button
          type="button"
          style={dangerButtonStyle}
          disabled={typedName !== binary.name || deleteMutation.isPending}
          onClick={handleDelete}
        >
          {deleteMutation.isPending ? "Deleting…" : "Delete"}
        </button>
      </div>
    </Dialog>
  );
}
