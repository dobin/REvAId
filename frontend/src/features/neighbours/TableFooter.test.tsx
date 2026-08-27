import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TableFooter } from "./TableFooter";

describe("TableFooter", () => {
  it("shows pagination counts and loads another bounded page", () => {
    const onLoadMore = vi.fn();
    render(<TableFooter shown={16} total={34} onLoadMore={onLoadMore} />);
    expect(screen.getByText("showing 16 of 34")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(onLoadMore).toHaveBeenCalledOnce();
  });

  it("hides Load more when every row is loaded", () => {
    render(<TableFooter shown={34} total={34} onLoadMore={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
    expect(screen.queryByText("showing 34 of 34")).not.toBeInTheDocument();
  });
});
