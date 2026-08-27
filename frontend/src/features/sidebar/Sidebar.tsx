/**
 * Sidebar (TAD §2.3) — hosts `PlaceEntryPointButton` (I6 stopgap) and
 * `OnCanvasList` (I6) above the `GlyphLegend`.
 */
import type { BinaryId, ViewId } from "@/api/types";
import { FunctionSearchInput } from "./FunctionSearchInput";
import { ImportBinaryButton } from "./ImportBinaryButton";
import { OnCanvasSearch } from "./OnCanvasSearch";
import { PlaceEntryPointButton } from "./PlaceEntryPointButton";
import { QueuePanel } from "./QueuePanel";
import { RebalanceButton } from "./RebalanceButton";
import { ResetCanvasButton } from "./ResetCanvasButton";
import { ResetSummariesButton } from "./ResetSummariesButton";
import { RuntimeBaseControl } from "./RuntimeBaseControl";
import { ViewPicker } from "./ViewPicker";

const sectionStyle: React.CSSProperties = {
  paddingTop: "0.875rem",
  paddingBottom: "0.875rem",
  borderTop: "1px solid #e5e7eb",
};

const sectionTitleStyle: React.CSSProperties = {
  fontSize: "0.75rem",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  color: "#6b7280",
  marginBottom: "0.5rem",
};

function SidebarSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section style={sectionStyle}>
      <h2 style={sectionTitleStyle}>{title}</h2>
      {children}
    </section>
  );
}

export function Sidebar({
  binaryName,
  binaryId,
  analysisImageBase,
  runtimeBase,
  onRuntimeBaseChange,
  viewId,
  onSelectView,
  onImported,
}: {
  binaryName: string | null;
  binaryId: BinaryId | null;
  analysisImageBase: number | null;
  runtimeBase: number | null;
  onRuntimeBaseChange: (value: number | null) => void;
  viewId: ViewId | null;
  onSelectView: (viewId: ViewId) => void;
  onImported: (binaryId: BinaryId) => void;
}) {
  return (
    <aside
      style={{
        width: "16rem",
        padding: "0 1rem",
        borderRight: "1px solid #e5e7eb",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <SidebarSection title="Binary">
        <ImportBinaryButton onImported={onImported} />
      </SidebarSection>
      {binaryId !== null && (
        <SidebarSection title="Runtime Address">
          <RuntimeBaseControl
            key={binaryId}
            analysisImageBase={analysisImageBase}
            runtimeBase={runtimeBase}
            onRuntimeBaseChange={onRuntimeBaseChange}
          />
        </SidebarSection>
      )}
      {binaryId !== null && (
        <SidebarSection title="Add Function">
          <FunctionSearchInput
            binaryId={binaryId}
            viewId={viewId}
            analysisImageBase={analysisImageBase}
            runtimeBase={runtimeBase}
          />
        </SidebarSection>
      )}
      <SidebarSection title="Find Function">
        <OnCanvasSearch
          binaryId={binaryId}
          viewId={viewId}
          analysisImageBase={analysisImageBase}
          runtimeBase={runtimeBase}
        />
      </SidebarSection>

      {binaryId !== null && binaryName !== null && (
        <SidebarSection title="View">
          <div
            style={{
              fontFamily: "var(--gr-font-mono, monospace)",
              fontSize: "0.875rem",
              color: "var(--gr-color-ground-truth, #111827)",
              marginBottom: "0.5rem",
            }}
          >
            {binaryName}
          </div>
          <ViewPicker binaryId={binaryId} value={viewId} onChange={onSelectView} />
        </SidebarSection>
      )}

      {viewId !== null ? (
        <SidebarSection title="Actions">
          {binaryId !== null && (
            <PlaceEntryPointButton binaryId={binaryId} viewId={viewId} />
          )}
          <RebalanceButton viewId={viewId} />
          <ResetCanvasButton viewId={viewId} />
          {binaryId !== null && <ResetSummariesButton binaryId={binaryId} />}
        </SidebarSection>
      ) : null}

      <SidebarSection title="LLM Activity">
        <QueuePanel />
      </SidebarSection>

    </aside>
  );
}
