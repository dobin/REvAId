/**
 * Sidebar (TAD §2.3) — hosts `PlaceEntryPointButton` (I6 stopgap) and
 * `OnCanvasList` (I6) above the `GlyphLegend`.
 */
import type { BinaryId, ViewId } from "@/api/types";
import { GlyphLegend } from "./GlyphLegend";
import { ImportBinaryButton } from "./ImportBinaryButton";
import { OnCanvasList } from "./OnCanvasList";
import { PlaceEntryPointButton } from "./PlaceEntryPointButton";
import { RebalanceButton } from "./RebalanceButton";
import { ResetCanvasButton } from "./ResetCanvasButton";

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
  binaryId,
  viewId,
  onImported,
}: {
  binaryId: BinaryId | null;
  viewId: ViewId | null;
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
      {viewId !== null ? (
        <SidebarSection title="Actions">
          {binaryId !== null && (
            <PlaceEntryPointButton binaryId={binaryId} viewId={viewId} />
          )}
          <RebalanceButton viewId={viewId} />
          <ResetCanvasButton viewId={viewId} />
        </SidebarSection>
      ) : null}
      <SidebarSection title="On canvas">
        <OnCanvasList viewId={viewId} />
      </SidebarSection>
      <SidebarSection title="Legend">
        <GlyphLegend />
      </SidebarSection>
    </aside>
  );
}
