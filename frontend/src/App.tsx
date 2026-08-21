import { useEffect, useState } from "react";
import { ConfigProvider } from "@/config/ConfigProvider";
import type { BinaryId, ViewId } from "@/api/types";
import { useBinariesQuery } from "@/api/queries/binaries";
import { useViewsQuery } from "@/api/queries/views";
import { Toolbar } from "@/features/toolbar/Toolbar";
import { Sidebar } from "@/features/sidebar/Sidebar";
import { CanvasView } from "@/features/canvas/CanvasView";
import { DetailPanel } from "@/features/detail/DetailPanel";

function AppShell() {
  const [selectedBinaryId, setSelectedBinaryId] = useState<BinaryId | null>(null);
  const [selectedViewId, setSelectedViewId] = useState<ViewId | null>(null);
  const binaries = useBinariesQuery();
  const views = useViewsQuery(selectedBinaryId);

  // Auto-select the first binary on initial load.
  useEffect(() => {
    if (selectedBinaryId !== null) return;
    const firstBinary = binaries.data?.[0];
    if (firstBinary) setSelectedBinaryId(firstBinary.id);
  }, [binaries.data, selectedBinaryId]);

  // Default to the binary's first view whenever the binary changes (or on
  // first load) and no view has been explicitly picked yet.
  useEffect(() => {
    if (selectedViewId !== null) return;
    const firstView = views.data?.[0];
    if (firstView) setSelectedViewId(firstView.id);
  }, [views.data, selectedViewId]);

  const handleSelectBinary = (binaryId: BinaryId) => {
    setSelectedBinaryId(binaryId);
    setSelectedViewId(null);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <Toolbar
        selectedBinaryId={selectedBinaryId}
        onSelectBinary={handleSelectBinary}
        selectedViewId={selectedViewId}
        onSelectView={setSelectedViewId}
      />
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar binaryId={selectedBinaryId} viewId={selectedViewId} />
        <main style={{ flex: 1, minWidth: 0 }}>
          <CanvasView selectedBinaryId={selectedBinaryId} viewId={selectedViewId} />
        </main>
        <DetailPanel />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ConfigProvider fallback={<p style={{ padding: "1rem" }}>Loading configuration…</p>}>
      <AppShell />
    </ConfigProvider>
  );
}
