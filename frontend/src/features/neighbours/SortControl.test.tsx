import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SortControl } from "./SortControl";

describe("SortControl", () => {
  it("calls onSortChange when the sort key changes", () => {
    const onSortChange = vi.fn();
    render(
      <SortControl
        sort="name"
        order="asc"
        onSortChange={onSortChange}
        onOrderChange={vi.fn()}
        label="Sort callees"
        direction="callees"
      />,
    );
    fireEvent.change(screen.getByLabelText("Sort callees"), { target: { value: "fanIn" } });
    expect(onSortChange).toHaveBeenCalledWith("fanIn");
  });

  it("toggles order on button click", () => {
    const onOrderChange = vi.fn();
    render(
      <SortControl
        sort="name"
        order="asc"
        onSortChange={vi.fn()}
        onOrderChange={onOrderChange}
        label="Sort callees"
        direction="callees"
      />,
    );
    fireEvent.click(screen.getByLabelText("Sort callees direction"));
    expect(onOrderChange).toHaveBeenCalledWith("desc");
  });

  it("shows only the active direction arrow", () => {
    const { rerender } = render(
      <SortControl
        sort="name"
        order="asc"
        onSortChange={vi.fn()}
        onOrderChange={vi.fn()}
        label="Sort callees"
        direction="callees"
      />,
    );
    expect(screen.getByLabelText("Sort ascending")).toBeInTheDocument();
    expect(screen.queryByText("asc")).not.toBeInTheDocument();

    rerender(
      <SortControl
        sort="name"
        order="desc"
        onSortChange={vi.fn()}
        onOrderChange={vi.fn()}
        label="Sort callees"
        direction="callees"
      />,
    );
    expect(screen.getByLabelText("Sort descending")).toBeInTheDocument();
    expect(screen.queryByText("desc")).not.toBeInTheDocument();
  });

  it("offers imported order only for callees", () => {
    const { rerender } = render(
      <SortControl
        sort="callOrder"
        order="asc"
        onSortChange={vi.fn()}
        onOrderChange={vi.fn()}
        label="Sort callees"
        direction="callees"
      />,
    );
    expect(screen.getByRole("option", { name: "Position" })).toBeInTheDocument();

    rerender(
      <SortControl
        sort="name"
        order="asc"
        onSortChange={vi.fn()}
        onOrderChange={vi.fn()}
        label="Sort callers"
        direction="callers"
      />,
    );
    expect(screen.queryByRole("option", { name: "Position" })).not.toBeInTheDocument();
  });
});
