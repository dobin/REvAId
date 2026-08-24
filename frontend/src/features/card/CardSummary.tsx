/**
 * Card-level summary area. Deliberately understated — plain muted text, no
 * italic/LLM-marker treatment (those are reserved for row-level truthfulness
 * marking, TAD §4.4) so the card summary reads as a normal one-line
 * description rather than the most dominant thing on the card. Renders
 * nothing for status="none" (no dash needed at card scale).
 *
 * I9 §5.3: `pending` shimmers instead of showing static "Generating…" text,
 * and `error` gains an inline retry button (regenerates at forced priority
 * 0, TAD C7) — this is the card-level counterpart to `SummaryCell`'s
 * row-level retry.
 */
import { Glyph } from "@/components/Glyph";
import type { FunctionDto } from "@/api/types";
import { useRegenerateSummaryMutation } from "@/api/queries/summaries";

export function CardSummary({ fn }: { fn: FunctionDto }) {
  const { status, short, lowConfidence, errorCode } = fn.summary;
  const regenerate = useRegenerateSummaryMutation();

  if (status === "none") return null;

  if (status === "pending") {
    return (
      <div style={{ padding: "0.375rem 0.75rem 0.25rem", fontSize: "0.75rem" }}>
        <span className="gr-shimmer">Generating summary…</span>
      </div>
    );
  }

  let text: string | null = null;
  let color = "#6b7280";

  switch (status) {
    case "ready":
      text = short;
      break;
    case "stale":
      text = short ? `${short} (stale)` : null;
      break;
    case "error":
      text = errorCode ?? "Summary failed";
      color = "#b91c1c";
      break;
    default:
      text = null;
  }

  if (!text) return null;

  return (
    <div
      title={fn.summary.long ?? text ?? undefined}
      style={{
        padding: "0.375rem 0.75rem 0.25rem",
        fontSize: "0.75rem",
        color,
        overflow: "hidden",
        display: "-webkit-box",
        WebkitLineClamp: 2,
        WebkitBoxOrient: "vertical",
      }}
    >
      {text}
      {status === "ready" && lowConfidence && " (low confidence)"}
      {status === "error" && (
        <button
          type="button"
          aria-label="Retry summary"
          title="Retry summary"
          onClick={(e) => {
            e.stopPropagation();
            regenerate.mutate(fn.id);
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
      )}
      {fn.summary.long && (
        <span
          style={{
            display: "inline-block",
            marginLeft: "0.25rem",
            fontSize: "0.65rem",
            lineHeight: 1,
            color: "#9ca3af",
            border: "1px solid #9ca3af",
            borderRadius: "50%",
            width: "0.9rem",
            height: "0.9rem",
            textAlign: "center",
            verticalAlign: "middle",
            flexShrink: 0,
          }}
        >
          i
        </span>
      )}
    </div>
  );
}
