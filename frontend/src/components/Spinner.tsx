/**
 * Small animated loading spinner (I9 §5.3). Replaces the static `◌` glyph
 * + grey `gr-shimmer` square that previously stood in for "summary
 * generating". Same visual footprint as a glyph so it drops into inline
 * text without disturbing line height.
 *
 * Respects `prefers-reduced-motion` (spins once to a stopped state).
 */
export function Spinner({
  size = "0.75rem",
  color = "#6b7280",
  label = "Loading",
}: {
  size?: string;
  color?: string;
  label?: string;
}) {
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className="gr-spinner"
      style={{
        display: "inline-block",
        width: size,
        height: size,
        flexShrink: 0,
        verticalAlign: "text-bottom",
        borderRadius: "50%",
        border: `1.5px solid ${color}`,
        borderTopColor: "transparent",
        animation: "gr-spin 0.7s linear infinite",
      }}
    />
  );
}
