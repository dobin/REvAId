/**
 * Empty canvas state (E1b) — shown before a binary is picked, or if a
 * picked binary has zero entry points.
 */
import { EmptyState } from "@/components/EmptyState";

export function CanvasEmptyState({ message }: { message: string }) {
  return <EmptyState title="Nothing on the canvas yet" description={message} />;
}
