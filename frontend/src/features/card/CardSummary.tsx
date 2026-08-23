/**
 * Card-level summary area. Deliberately understated — plain muted text, no
 * italic/LLM-marker treatment (those are reserved for row-level truthfulness
 * marking, TAD §4.4) so the card summary reads as a normal one-line
 * description rather than the most dominant thing on the card. Renders
 * nothing for status="none" (no dash needed at card scale).
 */
import type { FunctionDto } from "@/api/types";

export function CardSummary({ fn }: { fn: FunctionDto }) {
  const { status, short, lowConfidence, errorCode } = fn.summary;

  let text: string | null = null;
  let color = "#6b7280";

  switch (status) {
    case "none":
      return null;
    case "pending":
      text = "Generating summary…";
      break;
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
      title={text}
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
    </div>
  );
}
