import { useState } from "react";
import { Dialog } from "@/components/Dialog";
import type { BinaryId, ViewId } from "@/api/types";
import { FunctionSearchPanel } from "./FunctionSearchPanel";

export function FunctionSearchDialog({
  binaryId,
  viewId,
  analysisImageBase,
  runtimeBase,
  onRuntimeBaseChange,
}: {
  binaryId: BinaryId;
  viewId: ViewId | null;
  analysisImageBase: number | null;
  runtimeBase: number | null;
  onRuntimeBaseChange?: (value: number | null) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      title="Search functions"
      width="min(72rem, calc(100vw - 2rem))"
      trigger={
        <button
          type="button"
          disabled={viewId === null}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.625rem",
            width: "100%",
            padding: "0.625rem 0.75rem",
            marginBottom: "0.625rem",
            border: "1px solid #2563eb",
            borderRadius: "0.5rem",
            background: "#eff6ff",
            boxShadow: "0 2px 5px rgb(37 99 235 / 12%)",
            color: "#1d4ed8",
            cursor: viewId === null ? "not-allowed" : "pointer",
            fontSize: "0.875rem",
            fontWeight: 700,
            textAlign: "left",
            opacity: viewId === null ? 0.55 : 1,
          }}
        >
          <span
            aria-hidden="true"
            style={{
              display: "grid",
              placeItems: "center",
              width: "1.75rem",
              height: "1.75rem",
              borderRadius: "0.375rem",
              background: "#2563eb",
              color: "#ffffff",
              fontSize: "1.25rem",
              lineHeight: 1,
            }}
          >
            ⌕
          </span>
          <span>Search functions</span>
          <span aria-hidden="true" style={{ marginLeft: "auto", color: "#60a5fa" }}>→</span>
        </button>
      }
    >
      <FunctionSearchPanel
        binaryId={binaryId}
        viewId={viewId}
        analysisImageBase={analysisImageBase}
        runtimeBase={runtimeBase}
        {...(onRuntimeBaseChange && { onRuntimeBaseChange })}
      />
    </Dialog>
  );
}
