/**
 * Workspace view resolution (ADR 0006).
 *
 * Answers "which view should this browser open for this binary?" — the
 * single place that decides between the two modes:
 *
 * - **Private** (`publicMode: false`, the default): unchanged behaviour.
 *   Default to the binary's first view (B9 guarantees one exists after
 *   ingestion), and remember an explicit selection across binary switches
 *   within this page session.
 * - **Public** (`publicMode: true`): resolve from this browser's owned
 *   views (`lib/myViews`), creating a fresh view on first visit. Never
 *   falls back to the binary's first view — that one belongs to whoever
 *   ingested the binary, and landing an anonymous visitor on it is exactly
 *   the clobbering public mode exists to prevent.
 *
 * Returns `isResolving` while the (possible) creation round trip is in
 * flight so the caller can hold off rendering the canvas against a view
 * that is about to change.
 */
import { useEffect, useRef, useState } from "react";
import { useConfig } from "@/config/ConfigProvider";
import { useCreateViewMutation, useViewsQuery } from "@/api/queries/views";
import { getLatestMyViewId, recordMyView } from "@/lib/myViews";
import type { BinaryId, ViewId } from "@/api/types";

/** Fresh anonymous views get a stable, non-colliding name. The server does
 * not dedupe names (names are labels, §5.1), so a per-browser count is not
 * needed — the id is what isolates them. */
const ANONYMOUS_VIEW_NAME = "My view";

export function useWorkspaceView(binaryId: BinaryId | null): {
  viewId: ViewId | null;
  isResolving: boolean;
  selectView: (viewId: ViewId) => void;
} {
  const config = useConfig();
  // ADR 0006: the listing endpoint is closed in public mode, so the query is
  // disabled there — owned views come from `lib/myViews` instead. Private
  // mode still needs the listing to default to the binary's first view.
  const views = useViewsQuery(binaryId, { enabled: !config.publicMode });
  const createView = useCreateViewMutation(binaryId ?? 0);
  const [selectedViewId, setSelectedViewId] = useState<ViewId | null>(null);
  /** Guards the create-once race: Strict Mode double-effects and a slow
   * views query re-run must not create two anonymous views. */
  const creatingRef = useRef(false);

  // Reset selection whenever the binary changes — a view id from binary A
  // must never leak into binary B's workspace.
  useEffect(() => {
    setSelectedViewId(null);
    creatingRef.current = false;
  }, [binaryId]);

  useEffect(() => {
    if (binaryId === null || selectedViewId !== null) return;

    if (config.publicMode) {
      // Public mode: only ever resolve to a view this browser owns.
      const owned = getLatestMyViewId(binaryId);
      if (owned !== null) {
        setSelectedViewId(owned);
        return;
      }
      // First visit (or cleared storage): create the browser's own view.
      if (creatingRef.current) return;
      creatingRef.current = true;
      createView.mutate(
        { name: ANONYMOUS_VIEW_NAME },
        {
          onSuccess: (created) => {
            recordMyView(binaryId, created.id, created.name);
            setSelectedViewId(created.id);
          },
          onSettled: () => {
            creatingRef.current = false;
          },
        },
      );
      return;
    }

    // Private mode: default to the binary's first view (B9 guarantees at
    // least one exists after ingestion).
    const firstView = views.data?.[0];
    if (firstView) setSelectedViewId(firstView.id);
  }, [binaryId, selectedViewId, config.publicMode, views.isPending, views.data, createView]);

  const selectView = (viewId: ViewId): void => {
    // Ownership/name recording for public mode happens at the ViewPicker,
    // which knows the display name; this hook only switches the active view.
    setSelectedViewId(viewId);
  };

  return {
    viewId: selectedViewId,
    isResolving: selectedViewId === null,
    selectView,
  };
}
