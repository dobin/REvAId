/**
 * E5a "one event, all surfaces" for the C13 auto-display name: a `summary`
 * SSE event carrying `nameLlm` must patch `displayName`/`nameLlm` on BOTH
 * the function-detail cache entry AND every cached neighbour-page row —
 * no refetch, no reload (the bug this locks in: neighbour tables showed
 * `FUN_…` until a manual page reload).
 */
import { QueryClient, type InfiniteData } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { FunctionDto, NeighbourPageDto, SummaryEvent } from "@/api/types";
import { applySummaryEvent } from "./applyEvents";

// The card tables read from `useInfiniteNeighboursQuery`, whose cache key is
// `["neighbours-infinite", ...]` and whose value is `InfiniteData<
// NeighbourPageDto>` (`{ pages: [...] }`), NOT a bare page under
// `["neighbours", ...]`. Seeding the WRONG shape/key is exactly what let the
// original bug ship green — these keys/shapes mirror the real queries.
const INFINITE_KEY = ["neighbours-infinite", 1, 1, "callees", "primary"] as const;
const BARE_KEY = ["neighbours", 1, 1, "callees", "primary"] as const;

function makeInfinite(page = makeNeighbourPage()): InfiniteData<NeighbourPageDto> {
  return { pages: [page], pageParams: [0] };
}

let qc: QueryClient;

beforeEach(() => {
  qc = new QueryClient();
});

afterEach(() => {
  qc.clear();
});

function makeFunction(overrides: Partial<FunctionDto> = {}): FunctionDto {
  return {
    id: 17,
    binaryId: 1,
    address: 0x1000,
    displayName: "FUN_00001000",
    nameGhidra: "FUN_00001000",
    nameAnalyst: null,
    nameLlm: null,
    isRenamed: false,
    parameters: [],
    signature: null,
    kind: "normal",
    placeholderModule: null,
    fanIn: 0,
    fanOut: 1,
    isUtility: false,
    utilitySource: "computed",
    utilityOverride: null,
    summary: {
      status: "pending",
      short: null,
      long: null,
      model: null,
      adapter: null,
      errorCode: null,
      lowConfidence: false,
      generatedAt: null,
      isStale: false,
    },
    notes: "",
    hasNotes: false,
    notesUpdatedAt: null,
    calleeCount: 1,
    callerCount: 0,
    hasIndirectCalls: false,
    ...overrides,
  };
}

function makeNeighbourPage(): NeighbourPageDto {
  return {
    functionId: 1,
    direction: "callees",
    group: "primary",
    rows: [
      {
        id: 17,
        address: 0x1000,
        displayName: "FUN_00001000",
        nameLlm: null,
        isRenamed: false,
        summaryShort: null,
        summaryStatus: "pending",
        summaryLowConfidence: false,
        kind: "normal",
        onCanvas: false,
        isUtility: false,
        utilitySource: "computed",
        fanIn: 0,
        isSelf: false,
        hasNotes: false,
      },
    ],
    total: 1,
    totalPrimary: 1,
    totalUtility: 0,
    limit: 16,
    offset: 0,
    callersSuppressed: false,
    mayBeIncomplete: false,
  };
}

function summaryEvent(overrides: Partial<SummaryEvent> = {}): SummaryEvent {
  return {
    type: "summary",
    functionId: 17,
    summaryStatus: "ready",
    summaryShort: "Parses the header.",
    summaryModel: "stub",
    lowConfidence: false,
    generatedAt: "2026-08-26T00:00:00Z",
    errorCode: null,
    nameLlm: "parse_header",
    ...overrides,
  };
}

describe("applySummaryEvent name patching (C13 auto-display)", () => {
  it("patches displayName and nameLlm on the function cache entry", () => {
    qc.setQueryData(["function", 17], makeFunction());
    applySummaryEvent(qc, summaryEvent());
    const fn = qc.getQueryData<FunctionDto>(["function", 17]);
    expect(fn?.nameLlm).toBe("parse_header");
    expect(fn?.displayName).toBe("parse_header");
    expect(fn?.nameGhidra).toBe("FUN_00001000"); // never overwritten
    expect(fn?.summary.status).toBe("ready");
  });

  it("keeps the analyst name winning over the LLM proposal", () => {
    qc.setQueryData(
      ["function", 17],
      makeFunction({ nameAnalyst: "entry", displayName: "entry", isRenamed: true }),
    );
    applySummaryEvent(qc, summaryEvent());
    const fn = qc.getQueryData<FunctionDto>(["function", 17]);
    expect(fn?.displayName).toBe("entry");
    expect(fn?.nameLlm).toBe("parse_header"); // still exposed
  });

  it("patches the matching row in the infinite neighbour cache", () => {
    // This is the shape the app actually uses (useInfiniteNeighboursQuery).
    qc.setQueryData(INFINITE_KEY, makeInfinite());
    applySummaryEvent(qc, summaryEvent());
    const row = qc.getQueryData<InfiniteData<NeighbourPageDto>>(INFINITE_KEY)?.pages[0]?.rows[0];
    expect(row?.nameLlm).toBe("parse_header");
    expect(row?.displayName).toBe("parse_header");
    expect(row?.summaryShort).toBe("Parses the header.");
    expect(row?.summaryStatus).toBe("ready");
  });

  it("also patches the bare (single-page) neighbour cache", () => {
    qc.setQueryData(BARE_KEY, makeNeighbourPage());
    applySummaryEvent(qc, summaryEvent());
    const row = qc.getQueryData<NeighbourPageDto>(BARE_KEY)?.rows[0];
    expect(row?.nameLlm).toBe("parse_header");
    expect(row?.displayName).toBe("parse_header");
    expect(row?.summaryShort).toBe("Parses the header.");
  });

  it("leaves a renamed neighbour row's displayName untouched", () => {
    const page = makeNeighbourPage();
    const renamed = page.rows[0]!;
    renamed.isRenamed = true;
    renamed.displayName = "analyst_name";
    qc.setQueryData(INFINITE_KEY, makeInfinite(page));
    applySummaryEvent(qc, summaryEvent());
    const row = qc.getQueryData<InfiniteData<NeighbourPageDto>>(INFINITE_KEY)?.pages[0]?.rows[0];
    expect(row?.displayName).toBe("analyst_name");
    expect(row?.nameLlm).toBe("parse_header");
  });

  it("an event without a proposal (nameLlm null) keeps existing names", () => {
    qc.setQueryData(["function", 17], makeFunction());
    qc.setQueryData(INFINITE_KEY, makeInfinite());
    applySummaryEvent(qc, summaryEvent({ nameLlm: null }));
    expect(qc.getQueryData<FunctionDto>(["function", 17])?.displayName).toBe("FUN_00001000");
    const row = qc.getQueryData<InfiniteData<NeighbourPageDto>>(INFINITE_KEY)?.pages[0]?.rows[0];
    expect(row?.displayName).toBe("FUN_00001000");
    expect(row?.summaryStatus).toBe("ready"); // summary fields still patched
  });
});
