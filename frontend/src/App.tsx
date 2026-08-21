import { useState } from "react";
import { ConfigProvider } from "@/config/ConfigProvider";
import type { BinaryId } from "@/api/types";
import { Toolbar } from "@/features/toolbar/Toolbar";
import { Sidebar } from "@/features/sidebar/Sidebar";
import { CanvasView } from "@/features/canvas/CanvasView";

function AppShell() {
  const [selectedBinaryId, setSelectedBinaryId] = useState<BinaryId | null>(null);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <Toolbar selectedBinaryId={selectedBinaryId} onSelectBinary={setSelectedBinaryId} />
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar />
        <main style={{ flex: 1, minWidth: 0 }}>
          <CanvasView selectedBinaryId={selectedBinaryId} />
        </main>
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
