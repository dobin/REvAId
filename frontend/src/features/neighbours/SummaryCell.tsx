/**
 * Renders a row/card summary per `SummaryStatus` (§4.3 all table/card
 * states). No shimmer/animation in I5 — that polish arrives with I9's
 * demand system, which is what actually triggers generation.
 */
import { Glyph } from "@/components/Glyph";
import type { SummaryStatus } from "@/api/types";

export function SummaryCell({
  status,
  summaryShort,
  lowConfidence,
  errorCode,
}: {
  status: SummaryStatus;
  summaryShort: string | null;
  lowConfidence?: boolean;
  errorCode?: string | null;
}) {
  switch (status) {
    case "none":
      return <span style={{ color: "#9ca3af" }}>—</span>;
    case "pending":
      return (
        <span style={{ color: "#6b7280" }}>
          <Glyph name="generating" /> Generating…
        </span>
      );
    case "ready":
      return (
        <span className="gr-llm-output">
          <Glyph name="llmMarker" /> {summaryShort}
          {lowConfidence && " (low confidence)"}
        </span>
      );
    case "stale":
      return (
        <span className="gr-llm-output">
          <Glyph name="llmMarker" /> {summaryShort} (stale)
        </span>
      );
    case "error":
      return (
        <span style={{ color: "#b91c1c" }}>
          <Glyph name="error" /> {errorCode ?? "Summary failed"}
        </span>
      );
    default:
      return null;
  }
}
