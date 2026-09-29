import type { BinaryId, ViewId } from "@/api/types";
import { useNavigate } from "react-router";
import { FunctionSearchPanel } from "./FunctionSearchPanel";

export function SearchPage({
  binaryId,
  binaryName,
  viewId,
  analysisImageBase,
  runtimeBase,
}: {
  binaryId: BinaryId;
  binaryName: string;
  viewId: ViewId | null;
  analysisImageBase: number | null;
  runtimeBase: number | null;
}) {
  const navigate = useNavigate();
  const explorePath = `/${encodeURIComponent(binaryName)}/`;
  return (
    <main style={{ flex: 1, minWidth: 0, overflow: "auto", padding: "1.5rem" }}>
      <div style={{ maxWidth: "90rem", margin: "0 auto" }}>
        <h1 style={{ margin: "0 0 0.4rem", fontSize: "1.35rem" }}>Search functions</h1>
        <p style={{ margin: "0 0 1.25rem", color: "#6b7280", fontSize: "0.875rem" }}>
          Discover functions in <strong>{binaryName}</strong>. Select a result to add it to the active canvas.
        </p>
        <FunctionSearchPanel
          binaryId={binaryId}
          viewId={viewId}
          analysisImageBase={analysisImageBase}
          runtimeBase={runtimeBase}
          onOpenExisting={(functionId) => {
            void navigate(explorePath, { state: { focusFunctionId: functionId } });
          }}
          onAdded={() => { void navigate(explorePath); }}
        />
      </div>
    </main>
  );
}
