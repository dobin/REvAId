/**
 * Minimal view picker (I6, pulled forward from I10's full `ViewMenu`). A
 * plain select + "+ New view" prompt — no rename/delete/duplicate chrome
 * yet (that UI polish is deferred; the plain CRUD endpoints already exist).
 * Switching views calls `useSetLastViewMutation` (B16).
 */
import * as Select from "@radix-ui/react-select";
import { useCreateViewMutation, useSetLastViewMutation, useViewsQuery } from "@/api/queries/views";
import type { BinaryId, ViewId } from "@/api/types";

const sidebarLinkStyle: React.CSSProperties = {
  display: "block",
  padding: "0.125rem 0",
  marginBottom: "0.25rem",
  fontSize: "0.8125rem",
  textAlign: "left",
  background: "none",
  border: "none",
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
    <div>
      <Select.Root
        value={value !== null ? String(value) : ""}
        onValueChange={(next) => {
          selectView(Number(next));
        }}
      >
        <Select.Trigger
          aria-label="View"
          style={{
            ...sidebarLinkStyle,
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Select.Value placeholder="Select a view…" />
          <Select.Icon aria-hidden>⌄</Select.Icon>
        </Select.Trigger>
        <Select.Portal>
          <Select.Content>
            <Select.Viewport>
              {views.map((view) => (
                <Select.Item key={view.id} value={String(view.id)}>
                  <Select.ItemText>{view.name}</Select.ItemText>
                </Select.Item>
              ))}
            </Select.Viewport>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
      <button
        type="button"
        aria-label="New view"
        style={sidebarLinkStyle}
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
        + New view
      </button>
    </div>
  );
}
