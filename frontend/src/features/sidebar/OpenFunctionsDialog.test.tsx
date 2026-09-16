import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/api/client";
import type { OpenFunctionsResponseDto } from "@/api/types";
import { OpenFunctionsDialog } from "./OpenFunctionsDialog";

const response: OpenFunctionsResponseDto = {
  results: [
    {
      inputAddress: "0x180001000",
      status: "resolved",
      canonicalAddress: 0x401000,
      functionId: 7,
      displayName: "main",
      message: null,
    },
  ],
  nodes: [],
  rootFunctionId: 7,
};

function renderDialog(binaryLoadBase: number | null = null) {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <OpenFunctionsDialog viewId={5} binaryLoadBase={binaryLoadBase} />
    </QueryClientProvider>,
  );
}

describe("OpenFunctionsDialog", () => {
  afterEach(() => vi.restoreAllMocks());

  it("validates and submits pasted runtime addresses", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue(response);
    renderDialog();

    fireEvent.click(screen.getByRole("button", { name: /Open functions$/ }));
    fireEvent.change(screen.getByLabelText("DLL load base"), { target: { value: "0x180000000" } });
    fireEvent.change(screen.getByLabelText("Function addresses"), {
      target: { value: "0x180001000, 0x180002000" },
    });
    const buttons = screen.getAllByRole("button", { name: "Open functions" });
    const submitButton = buttons.at(-1);
    expect(submitButton).toBeDefined();
    fireEvent.click(submitButton as HTMLElement);

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith("/views/5/open-functions", {
        addresses: ["0x180001000", "0x180002000"],
        dllBase: "0x180000000",
      });
    });
    expect(await screen.findByText(/resolved — main/)).toBeInTheDocument();
  });

  it("defaults the DLL base to the binary base", () => {
    renderDialog(0x180000000);

    fireEvent.click(screen.getByRole("button", { name: /Open functions$/ }));

    expect(screen.getByLabelText("DLL load base")).toHaveValue("0x180000000");
  });

  it("falls back to the standard image base when the binary has none", () => {
    renderDialog();

    fireEvent.click(screen.getByRole("button", { name: /Open functions$/ }));

    expect(screen.getByLabelText("DLL load base")).toHaveValue("0x140000000");
  });

  it("shows malformed automatic payload errors", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <OpenFunctionsDialog
          viewId={5}
          binaryLoadBase={null}
          automaticError="open_functions is not valid JSON."
          automaticKey="?bad"
        />
      </QueryClientProvider>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("open_functions is not valid JSON.");
  });
});
