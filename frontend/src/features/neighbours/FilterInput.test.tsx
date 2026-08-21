import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FilterInput } from "./FilterInput";

describe("FilterInput", () => {
  it("calls onFilterChange with the empty string on mount", () => {
    const onFilterChange = vi.fn();
    render(<FilterInput label="Filter callees" onFilterChange={onFilterChange} />);
    expect(onFilterChange).toHaveBeenCalledWith("");
  });

  it("debounces onFilterChange while typing", async () => {
    const onFilterChange = vi.fn();
    render(<FilterInput label="Filter callees" onFilterChange={onFilterChange} />);

    const input = screen.getByLabelText("Filter callees");
    fireEvent.change(input, { target: { value: "parse" } });

    await waitFor(() => {
      expect(onFilterChange).toHaveBeenLastCalledWith("parse");
    });
  });
});
