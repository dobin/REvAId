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
 *
 * The full `short` + `long` text used to hide behind a native `title=`
 * tooltip — a hover-only wall of small text you couldn't scroll or read
 * comfortably. It's now a click-to-open Radix `SummaryPopover` (Esc /
 * click-outside / click-again to close, formatted via the shared
 * `SummaryBody`). The inline card text stays a 2-line clamp; a small circled
 * "i" marks that more is available on click.
 */
import { useState } from "react";
import { Glyph } from "@/components/Glyph";
import { Spinner } from "@/components/Spinner";
import { SummaryPopover } from "@/components/SummaryPopover";
import { SummaryBody } from "@/components/SummaryBody";
import type { FunctionDto } from "@/api/types";
import { useRegenerateSummaryMutation } from "@/api/queries/summaries";

export function CardSummary({ fn }: { fn: FunctionDto }) {
  const { status, short, lowConfidence, errorCode } = fn.summary;
  const regenerate = useRegenerateSummaryMutation();
  const [popoverOpen, setPopoverOpen] = useState(false);

  if (status === "none") return null;

  if (status === "pending") {
    return (
      <div style={{ padding: "0.375rem 0.75rem 0.25rem", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "0.375rem", color: "#6b7280" }}>
        <Spinner label="Summary generating" /> Generating summary…
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

  // The error state keeps its inline retry button and is never expandable —
  // there's no `short`/`long` prose to read. Every other state (ready/stale)
  // opens the click popover with the full summary.
  if (status === "error") {
    return (
      <div style={summaryTextStyle(color)}>
        {text}
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
      </div>
    );
  }

  return (
    <div style={{ padding: "0.375rem 0.75rem 0.25rem" }}>
      <SummaryPopover
        open={popoverOpen}
        onOpenChange={setPopoverOpen}
        trigger={
          <button
            type="button"
            aria-label="Show full summary"
            title="Show full summary"
            // Opening the popover must not also select the card / open the
            // detail panel (the card header wraps this in a click-to-select
            // handler).
            onClick={(e) => {
              e.stopPropagation();
            }}
            style={{
              width: "100%",
              margin: 0,
              padding: 0,
              border: "none",
              background: "none",
              font: "inherit",
              fontSize: "0.75rem",
              color,
              textAlign: "left",
              cursor: "pointer",
              overflow: "hidden",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
            }}
          >
            {text}
            {status === "ready" && lowConfidence && " (low confidence)"}
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
          </button>
        }
      >
        <SummaryBody status={status} short={short} long={fn.summary.long} />
      </SummaryPopover>
    </div>
  );
}

function summaryTextStyle(color: string): React.CSSProperties {
  return {
    padding: "0.375rem 0.75rem 0.25rem",
    fontSize: "0.75rem",
    color,
    overflow: "hidden",
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
  };
}
