import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router";
import { ConfigProvider } from "@/config/ConfigProvider";
import type { BinaryId, ViewId } from "@/api/types";
import { useBinariesQuery } from "@/api/queries/binaries";
import { useViewsQuery } from "@/api/queries/views";
import { Toolbar } from "@/features/toolbar/Toolbar";
import { Sidebar } from "@/features/sidebar/Sidebar";
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
  const [selectedViewId, setSelectedViewId] = useState<ViewId | null>(null);

  const binary = binaries?.find((candidate) => candidate.name === binaryName) ?? null;
  const selectedBinaryId: BinaryId | null = binary?.id ?? null;
  const views = useViewsQuery(selectedBinaryId);

  // Default to the binary's first view whenever the binary changes (or on
  // first load) and no view has been explicitly picked yet.
  useEffect(() => {
    if (selectedViewId !== null) return;
    const firstView = views.data?.[0];
    if (firstView) setSelectedViewId(firstView.id);
  }, [views.data, selectedViewId]);

  // Reset the view selection when navigating to a different binary.
  useEffect(() => {
    setSelectedViewId(null);
  }, [binaryName]);

  if (isPending) {
    return <EmptyState title="Loading binaries…" />;
  }
  if (isError) {
    return <EmptyState title="Could not load binaries." />;
  }
  if (binary === null) {
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

  const handleImported = (binaryId: BinaryId) => {
    const imported = (binaries ?? []).find((candidate) => candidate.id === binaryId);
    if (imported) {
      navigate(`/${encodeURIComponent(imported.name)}/`, { replace: true });
    } else {
      navigate("/", { replace: true });
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
            viewId={selectedViewId}
            onSelectView={setSelectedViewId}
            onImported={handleImported}
          />
          <main style={{ flex: 1, minWidth: 0 }}>
            <CanvasView selectedBinaryId={selectedBinaryId} viewId={selectedViewId} actionsRegistry={actionsRegistry} />
          </main>
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
      navigate(`${location.pathname}/`, { replace: true });
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
