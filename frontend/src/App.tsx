import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router";
import { ConfigProvider } from "@/config/ConfigProvider";
import type { BinaryId } from "@/api/types";
import { useBinariesQuery } from "@/api/queries/binaries";
import { useWorkspaceView } from "@/hooks/useWorkspaceView";
import { Toolbar } from "@/features/toolbar/Toolbar";
import { Sidebar } from "@/features/sidebar/Sidebar";
import { AutoPlaceEntryPoint } from "@/features/sidebar/PlaceEntryPointButton";
import { CanvasView } from "@/features/canvas/CanvasView";
import { DetailPanel } from "@/features/detail/DetailPanel";
import { BinariesPage } from "@/features/binaries/BinariesPage";
import { EmptyState } from "@/components/EmptyState";
import { CanvasActionsRegistryProvider, useCreateCanvasActionsRegistry } from "@/features/canvas/CanvasActions";
import { SseProvider } from "@/realtime/SseProvider";

/**
 * The workspace shell for one open binary, keyed by the binary's name in the
 * URL path (`/{binaryName}/`). Resolves the name against `GET /binaries`;
 * while loading or when the name is unknown we show a placeholder instead of
 * the graph.
 */
function BinaryWorkspace({ binaryName }: { binaryName: string }) {
  const actionsRegistry = useCreateCanvasActionsRegistry();
  const navigate = useNavigate();
  const { data: binaries, isPending, isError } = useBinariesQuery();
  const [runtimeBase, setRuntimeBase] = useState<number | null>(null);

  const binary = binaries?.find((candidate) => candidate.name === binaryName);
  const selectedBinaryId: BinaryId | null = binary?.id ?? null;
  // ADR 0006: the single view-resolution point. Private mode defaults to
  // the binary's first view; public mode resolves/creates this browser's
  // own anonymous view and never falls back to a shared one.
  const { viewId: selectedViewId, isResolving, selectView } = useWorkspaceView(selectedBinaryId);

  // Reset the runtime base when navigating to a different binary.
  useEffect(() => {
    setRuntimeBase(null);
  }, [binaryName]);

  if (isPending) {
    return <EmptyState title="Loading binaries…" />;
  }
  if (isError) {
    return <EmptyState title="Could not load binaries." />;
  }
  if (!binary) {
    return (
      <EmptyState
        title={`Binary “${binaryName}” not found.`}
        description="It may have been deleted or renamed."
        action={
          <Link to="/" style={{ color: "var(--gr-color-ground-truth, #111827)" }}>
            ← All binaries
          </Link>
        }
      />
    );
  }

  // Public mode may still be creating this browser's first view — hold the
  // canvas rather than flashing it against a view id that is about to land.
  if (isResolving) {
    return <EmptyState title="Preparing view…" />;
  }

  const handleImported = (binaryId: BinaryId) => {
    const imported = binaries.find((candidate) => candidate.id === binaryId);
    if (imported) {
      void navigate(`/${encodeURIComponent(imported.name)}/`, { replace: true });
    } else {
      void navigate("/", { replace: true });
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <Toolbar
      />
      <CanvasActionsRegistryProvider value={actionsRegistry}>
        <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
          <Sidebar
            binaryName={binary.name}
            binaryId={selectedBinaryId}
            analysisImageBase={binary.analysisImageBase}
            runtimeBase={runtimeBase}
            onRuntimeBaseChange={setRuntimeBase}
            viewId={selectedViewId}
            onSelectView={selectView}
            onImported={handleImported}
          />
          <main style={{ flex: 1, minWidth: 0 }}>
            <CanvasView selectedBinaryId={selectedBinaryId} viewId={selectedViewId} actionsRegistry={actionsRegistry} />
          </main>
          {selectedBinaryId !== null && selectedViewId !== null && (
            <AutoPlaceEntryPoint
              key={selectedViewId}
              binaryId={selectedBinaryId}
              viewId={selectedViewId}
            />
          )}
          <DetailPanel />
        </div>
      </CanvasActionsRegistryProvider>
    </div>
  );
}

/**
 * Normalizes the `:binaryName` segment (URL-decoded by the router) and
 * redirects `/name` → `/name/` so both spellings land on the canonical form.
 */
function BinaryWorkspaceRoute() {
  const location = useLocation();
  const navigate = useNavigate();
  const binaryName = decodeURIComponent(
    location.pathname.replace(/^\//, "").replace(/\/+$/, ""),
  );

  useEffect(() => {
    if (!location.pathname.endsWith("/")) {
      void navigate(`${location.pathname}/`, { replace: true });
    }
  }, [location.pathname, navigate]);

  if (!location.pathname.endsWith("/")) return <EmptyState title="Redirecting…" />;
  return <BinaryWorkspace binaryName={binaryName} />;
}

function AppShell() {
  return (
    <Routes>
      <Route path="/" element={<BinariesPage />} />
      <Route path="/:binaryName" element={<BinaryWorkspaceRoute />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ConfigProvider fallback={<p style={{ padding: "1rem" }}>Loading configuration…</p>}>
      <SseProvider>
        <AppShell />
      </SseProvider>
    </ConfigProvider>
  );
}
