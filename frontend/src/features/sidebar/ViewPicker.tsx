/**
 * Minimal view picker (I6, pulled forward from I10's full `ViewMenu`). A
 * compact native select + new-view action — no rename/delete/duplicate chrome
 * yet (that UI polish is deferred; the plain CRUD endpoints already exist).
 * Switching views calls `useSetLastViewMutation` (B16).
 */
import { useCreateViewMutation, useSetLastViewMutation, useViewsQuery } from "@/api/queries/views";
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
  const { data: views, isPending, isError } = useViewsQuery(binaryId);
  const createView = useCreateViewMutation(binaryId);
  const setLastView = useSetLastViewMutation(binaryId);

  if (isPending) return <span>Loading views…</span>;
  if (isError) return <span>Could not load views.</span>;

  const selectView = (viewId: ViewId) => {
    onChange(viewId);
    setLastView.mutate({ viewId });
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
      <select
        aria-label="View"
        style={selectStyle}
        value={value !== null ? String(value) : ""}
        onChange={(event) => {
          selectView(Number(event.target.value));
        }}
      >
        <option value="" disabled>
          Select a view…
        </option>
        {views.map((view) => (
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
                selectView(created.id);
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
