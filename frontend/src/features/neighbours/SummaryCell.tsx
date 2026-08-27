/**
 * Renders a row/card summary per `SummaryStatus` (§4.3 all table/card
 * states). I9 §5.3 finishes the states left as plain text in I5: `pending`
 * shimmers (`.gr-shimmer`, `styles/tokens.css`) instead of static text, and
 * `error` gains a retry button (only rendered when `functionId` is passed —
 * omit it for read-only/isolated rendering).
 */
import { Glyph } from "@/components/Glyph";
import { Spinner } from "@/components/Spinner";
import type { FunctionId, SummaryStatus } from "@/api/types";
import { useRegenerateSummaryMutation } from "@/api/queries/summaries";

export function SummaryCell({
  status,
  summaryShort,
  lowConfidence,
  errorCode,
  functionId,
}: {
  status: SummaryStatus;
  summaryShort: string | null;
  lowConfidence?: boolean;
  errorCode?: string | null;
  /** Enables the retry-on-error affordance. Omitted in isolated/unit
   * rendering that has no mutation/QueryClient context to call into. */
  functionId?: FunctionId;
}) {
  switch (status) {
    case "none":
      return <span style={{ color: "#9ca3af" }}>—</span>;
    case "pending":
      return (
        <span style={{ color: "#6b7280", display: "inline-flex", alignItems: "center", gap: "0.375rem" }}>
          <Spinner label="Summary generating" /> Generating…
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
          {functionId !== undefined && <RetryButton functionId={functionId} />}
        </span>
      );
    default:
      return null;
  }
}

function RetryButton({ functionId }: { functionId: FunctionId }) {
  const regenerate = useRegenerateSummaryMutation();
  return (
    <button
      type="button"
      aria-label="Retry summary"
      title="Retry summary"
      onClick={(e) => {
        e.stopPropagation();
        regenerate.mutate(functionId);
      }}
      disabled={regenerate.isPending}
      style={{
        border: "none",
        background: "none",
        cursor: regenerate.isPending ? "default" : "pointer",
        padding: "0 0.25rem",
        color: "inherit",
      }}
    >
      <Glyph name="retry" />
    </button>
  );
}
