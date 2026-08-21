import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders title and optional description", () => {
    render(<EmptyState title="No binaries" description="Ingest one to get started." />);
    expect(screen.getByText("No binaries")).toBeInTheDocument();
    expect(screen.getByText("Ingest one to get started.")).toBeInTheDocument();
  });

  it("renders an optional action node", () => {
    render(<EmptyState title="No binaries" action={<button>Retry</button>} />);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
