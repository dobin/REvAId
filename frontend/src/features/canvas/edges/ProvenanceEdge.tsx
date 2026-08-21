/**
 * Canvas edge (TAD §2.3) — solid for a real call-graph link, dashed when
 * `originImplied` (D17: a callstack frame with no matching `edges` row).
 * Rendered purely from `deriveCanvasEdges`'s output; never from `edges`.
 */
import { BaseEdge, getStraightPath, type EdgeProps } from "@xyflow/react";

export function ProvenanceEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
}: EdgeProps) {
  const [path] = getStraightPath({ sourceX, sourceY, targetX, targetY });
  const implied = Boolean((data as { implied?: boolean } | undefined)?.implied);

  return (
    <BaseEdge
      path={path}
      style={{
        stroke: "#9ca3af",
        strokeWidth: 1.5,
        strokeDasharray: implied ? "4 4" : undefined,
      }}
    />
  );
}
