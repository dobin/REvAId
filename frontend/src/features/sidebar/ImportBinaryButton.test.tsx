import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/api/client";
import type { ImportJobAcceptedDto, ImportJobStatusDto } from "@/api/types";
import { ImportBinaryButton } from "./ImportBinaryButton";

function renderButton(onImported = vi.fn()) {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <ImportBinaryButton onImported={onImported} />
    </QueryClientProvider>,
  );
  return { onImported };
}

function jsonFile(name: string, content: string): File {
  const file = new File([content], name, { type: "application/json" });
  // jsdom's File.text() is unreliable across versions; back it with the content.
  Object.defineProperty(file, "text", { value: () => Promise.resolve(content) });
  return file;
}

function openDialogAndUpload(file: File) {
  fireEvent.click(screen.getByRole("button", { name: /\(re\) import binary/i }));
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ImportBinaryButton", () => {
  it("shows an inline error for a non-JSON file", async () => {
    renderButton();
    openDialogAndUpload(jsonFile("bad.json", "not json{"));

    expect(
      await screen.findByText(/could not read the file|not a ghidra|unexpected|json/i),
    ).toBeInTheDocument();
  });

  it("refreshes after the import job completes, then calls onImported", async () => {
    const accepted: ImportJobAcceptedDto = {
      jobId: "job-1",
      phase: "queued",
      bytesReceived: 123,
    };
    const completed: ImportJobStatusDto = {
      jobId: "job-1",
      phase: "completed",
      bytesReceived: 123,
      result: {
        binaryId: 42,
        name: "sample.exe",
        version: "1.0",
        functionsInserted: 2,
        functionsUpdated: 0,
        edgesInserted: 1,
        placeholdersCreated: 0,
        failures: [],
      },
      errorMessage: null,
      failureSamples: [],
    };
    const post = vi.spyOn(apiClient, "post").mockResolvedValue(accepted);
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(completed);

    const { onImported } = renderButton();
    const doc = JSON.stringify({
      schemaVersion: 1,
      binary: { name: "sample.exe", version: "1.0" },
      functions: [{}, {}],
      edges: [{}],
    });
    openDialogAndUpload(jsonFile("sample.json", doc));

    expect(await screen.findByText(/ready to import/i)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Import"));

    await waitFor(() => {
      expect(onImported).toHaveBeenCalledWith(42);
    });
    expect(post).toHaveBeenCalledWith(
      "/binaries/import",
      expect.objectContaining({ schemaVersion: 1 }),
    );
    expect(get).toHaveBeenCalledWith("/binaries/imports/job-1");
  });

  it("shows an error rather than reporting success when the import job fails", async () => {
    vi.spyOn(apiClient, "post").mockResolvedValue({
      jobId: "job-1",
      phase: "queued",
      bytesReceived: 123,
    });
    vi.spyOn(apiClient, "get").mockResolvedValue({
      jobId: "job-1",
      phase: "failed",
      bytesReceived: 123,
      result: null,
      errorMessage: "The export is invalid.",
      failureSamples: ["missing functions"],
    });

    const { onImported } = renderButton();
    const doc = JSON.stringify({
      schemaVersion: 1,
      binary: { name: "sample.exe", version: "1.0" },
      functions: [],
      edges: [],
    });
    openDialogAndUpload(jsonFile("sample.json", doc));
    fireEvent.click(await screen.findByText("Import"));

    expect(await screen.findByText("The export is invalid.")).toBeInTheDocument();
    expect(onImported).not.toHaveBeenCalled();
  });
});
