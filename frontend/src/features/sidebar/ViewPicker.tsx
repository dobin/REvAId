/**
 * Minimal view picker (I6, pulled forward from I10's full `ViewMenu`). A
 * compact native select + new-view action — no rename/delete/duplicate chrome
 * yet (that UI polish is deferred; the plain CRUD endpoints already exist).
 *
 * Mode split (ADR 0006): private instances list all of the binary's views
 * via `useViewsQuery` and persist switches via `useSetLastViewMutation`
 * (B16). Public mode lists only this browser's owned views from
 * `lib/myViews` (the listing endpoint is closed) and skips the shared
 * `last-view` write — a server-side pointer is meaningless across anonymous
 * browsers and they would fight over it.
 */
import { useConfig } from "@/config/ConfigProvider";
import { useCreateViewMutation, useSetLastViewMutation, useViewsQuery } from "@/api/queries/views";
import { getMyViews, recordMyView } from "@/lib/myViews";
import type { BinaryId, ViewId } from "@/api/types";

const selectStyle: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  padding: "0.25rem 0.375rem",
  fontSize: "0.8125rem",
  textAlign: "left",
  border: "1px solid #d1d5db",
  borderRadius: "0.25rem",
  background: "#ffffff",
  color: "#111827",
  cursor: "pointer",
};

const addButtonStyle: React.CSSProperties = {
  width: "1.75rem",
  height: "1.75rem",
  padding: 0,
  fontSize: "1.125rem",
  lineHeight: 1,
  border: "1px solid #d1d5db",
  borderRadius: "0.25rem",
  background: "#ffffff",
  cursor: "pointer",
};

export function ViewPicker({
  binaryId,
  value,
  onChange,
}: {
  binaryId: BinaryId;
  value: ViewId | null;
  onChange: (viewId: ViewId) => void;
}) {
  const config = useConfig();
  // ADR 0006: disabled in public mode (the listing endpoint is closed); owned
  // views come from `lib/myViews` below. `views` is only meaningful when
  // `!config.publicMode`, so it is typed/narrowed accordingly.
  const views = useViewsQuery(binaryId, { enabled: !config.publicMode });
  const createView = useCreateViewMutation(binaryId);
  const setLastView = useSetLastViewMutation(binaryId);

  if (!config.publicMode && views.isPending) return <span>Loading views…</span>;
  if (!config.publicMode && views.isError) return <span>Could not load views.</span>;

  // Public mode: only this browser's own views are listed/selectable —
  // other visitors' (and the owner's) views stay invisible, which is the
  // isolation ADR 0006 is about. `getMyViews` reads localStorage, so the
  // list is per-browser by construction and needs no network call.
  const ownedViews = config.publicMode ? getMyViews(binaryId) : null;
  const options = ownedViews ?? (views.data ?? []);

  const selectView = (viewId: ViewId, name: string) => {
    onChange(viewId);
    if (config.publicMode) {
      recordMyView(binaryId, viewId, name);
    } else {
      setLastView.mutate({ viewId });
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
      <select
        aria-label="View"
        style={selectStyle}
        value={value !== null && options.some((v) => v.id === value) ? String(value) : ""}
        onChange={(event) => {
          const viewId = Number(event.target.value);
          const name = options.find((v) => v.id === viewId)?.name ?? String(viewId);
          selectView(viewId, name);
        }}
      >
        <option value="" disabled>
          Select a view…
        </option>
        {options.map((view) => (
          <option key={view.id} value={String(view.id)}>
            {view.name}
          </option>
        ))}
      </select>
      <button
        type="button"
        aria-label="New view"
        title="New view"
        style={addButtonStyle}
        onClick={() => {
          const name = window.prompt("New view name");
          if (!name) return;
          createView.mutate(
            { name },
            {
              onSuccess: (created) => {
                if (config.publicMode) {
                  recordMyView(binaryId, created.id, created.name);
                }
                selectView(created.id, created.name);
              },
            },
          );
        }}
      >
        +
      </button>
    </div>
  );
}
