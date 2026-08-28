/**
 * Curated TypeScript DTOs (TAD §3.4). Component code imports from here, never
 * from `generated.ts` directly — this is the one place that reconciles the
 * OpenAPI-generated shapes with the hand-written aliases the rest of the app
 * depends on.
 *
 * Written in full now (I1) so later increments (I5+) have real types to
 * import instead of inventing ad hoc shapes per component.
 */

export type FunctionId = number;
export type BinaryId = number;
export type ViewId = number;

export type FunctionKind = "normal" | "import" | "thunk" | "external" | "placeholder";
// D-3: PRD Module-B says `call` is the only M0 value; edges.kind is narrowed
// here to match the DB CHECK constraint. Widen in the A10 migration.
export type EdgeKind = "call";
export type SummaryStatus = "none" | "pending" | "ready" | "error" | "stale";
// `fanin` is like `fanout` but the derived canvas edge is oriented from the
// new node to the card it was spawned from, so ELK (direction RIGHT) places a
// fanned-out *caller* to the left (deriveCanvasEdges).
export type OriginKind = "root" | "fanout" | "callstack" | "fanin";
export type UtilitySource = "computed" | "analyst";
export type UtilityOverride = "always" | "never" | null;
// D16: "a small palette of named tokens, not free-form hex". No PRD-specified
// token list exists beyond `red` (J2); this set is a TAD invention.
export type NodeColor = "slate" | "red" | "amber" | "green" | "blue" | "violet" | "pink";
export type Priority = 0 | 1 | 2 | 3;

export interface BinarySummaryDto {
  id: BinaryId;
  name: string;
  version: string;
  analysisImageBase: number | null;
  functionCount: number;
  edgeCount: number;
  lastViewId: ViewId | null;
  createdAt: string;
}

/**
 * A Ghidra JSON export document — the `POST /binaries/import` request body
 * (I12). Produced by `tools/ghidra/GraphRevExport.java` (schemas v1/v2). Typed
 * loosely here (functions/edges as `unknown[]`) since the file is parsed and
 * validated server-side; the client only needs to POST the parsed JSON.
 */
export interface GhidraExportDocument {
  schemaVersion: number;
  binary: {
    name: string;
    version?: string;
    sourcePath?: string | null;
    analysisImageBase?: number | null;
    sha256?: string | null;
    functionCount?: number | null;
    edgeCount?: number | null;
  };
  functions: unknown[];
  edges: unknown[];
}

/** Completed import result, included in a completed import-job status. */
export interface ImportResultDto {
  binaryId: BinaryId;
  name: string;
  version: string;
  functionsInserted: number;
  functionsUpdated: number;
  edgesInserted: number;
  placeholdersCreated: number;
  failures: string[];
}

export type ImportJobPhase = "uploading" | "queued" | "importing" | "completed" | "failed" | "cancelled";

/** `POST /binaries/import` response. The import continues asynchronously. */
export interface ImportJobAcceptedDto {
  jobId: string;
  phase: ImportJobPhase;
  bytesReceived: number;
}

/** `GET /binaries/imports/{jobId}` response. */
export interface ImportJobStatusDto {
  jobId: string;
  phase: ImportJobPhase;
  bytesReceived: number;
  result: ImportResultDto | null;
  errorMessage: string | null;
  failureSamples: string[];
}

export interface FunctionParam {
  ordinal: number;
  name: string;
  type: string;
}

/** Full function record — detail panel + card. */
export interface FunctionDto {
  id: FunctionId;
  binaryId: BinaryId;
  address: number; // render as hex in UI only (AS7)
  displayName: string; // name_analyst ?? name_llm ?? name_ghidra (B6 + C13 auto-display)
  nameGhidra: string;
  nameAnalyst: string | null;
  // C13 auto-display: LLM-proposed name; displayName already reflects the
  // precedence — exposed so the UI can show the raw Ghidra name as a
  // secondary label when the LLM name overrides it.
  nameLlm: string | null;
  isRenamed: boolean;
  parameters: FunctionParam[];
  signature: string | null;
  kind: FunctionKind;
  placeholderModule: string | null;
  fanIn: number;
  fanOut: number;
  isUtility: boolean; // EFFECTIVE (override applied) — E2b/Q25
  utilitySource: UtilitySource;
  utilityOverride: UtilityOverride;
  summary: {
    status: SummaryStatus;
    short: string | null;
    long: string | null;
    model: string | null;
    // I13/AM4: which adapter produced the summary ("mock"/"litellm"/...).
    // Hand-mirrored from FunctionSummaryStateDto; no UI affordance yet.
    adapter: string | null;
    errorCode: string | null;
    lowConfidence: boolean;
    generatedAt: string | null;
    isStale: boolean;
  };
  notes: string;
  hasNotes: boolean;
  notesUpdatedAt: string | null;
  calleeCount: number;
  callerCount: number;
  hasIndirectCalls: boolean; // §5.1 table footer hint
}

/** One row in a card's caller/callee table. Deliberately narrow. */
export interface NeighbourRowDto {
  id: FunctionId;
  address: number;
  displayName: string;
  // C13 auto-display: LLM-proposed name (displayName already reflects the
  // name_analyst ?? name_llm ?? name_ghidra precedence).
  nameLlm: string | null;
  isRenamed: boolean;
  summaryShort: string | null;
  summaryStatus: SummaryStatus;
  summaryLowConfidence: boolean;
  kind: FunctionKind;
  onCanvas: boolean; // view-scoped → E2 requires viewId
  isUtility: boolean; // effective
  utilitySource: UtilitySource;
  fanIn: number;
  isSelf: boolean; // ↻ recursion, fan-out disabled
  hasNotes: boolean;
}

export interface NeighbourPageDto {
  functionId: FunctionId;
  direction: "callees" | "callers";
  group: "primary" | "utility";
  rows: NeighbourRowDto[]; // pre-ordered, utility last (E2b)
  total: number;
  totalPrimary: number;
  totalUtility: number; // drives "▸ ▫ utility calls (N)"
  limit: number;
  offset: number;
  callersSuppressed: boolean; // E2a
  mayBeIncomplete: boolean; // §5.1 indirect-call footer
}

export interface ViewNodeDto {
  functionId: FunctionId;
  visible: boolean;
  collapsed: boolean;
  color: NodeColor | null;
  posX: number;
  posY: number;
  pinned: boolean;
  originFunctionId: FunctionId | null;
  originKind: OriginKind;
  originImplied: boolean;
}

export interface ViewDto {
  id: ViewId;
  binaryId: BinaryId;
  name: string;
  rootFunctionId: FunctionId | null;
  camera: { x: number; y: number; zoom: number };
  nodes: ViewNodeDto[];
  createdAt: string;
  updatedAt: string;
}

/**
 * Narrow, read-only view record (I5 — pulled forward from I6's full
 * `ViewDto` just far enough to resolve a `viewId` for the neighbours
 * endpoint). No `camera`, no `nodes[]` — those arrive with I6's full CRUD.
 */
export interface ViewSummaryDto {
  id: ViewId;
  binaryId: BinaryId;
  name: string;
  rootFunctionId: FunctionId | null;
  createdAt: string;
  updatedAt: string;
}
/** `POST /binaries/{id}/views` request body (I6). */
export interface ViewCreateRequest {
  name: string;
}

/** `PATCH /views/{id}` request body (I6/E3a) — every field optional. */
export interface ViewPatchRequest {
  name?: string;
  rootFunctionId?: FunctionId | null;
  camera?: { x: number; y: number; zoom: number };
}

/** One entry in a `PATCH /views/{id}/nodes` upsert array (I6/E3). Every
 * field but `functionId` is optional — omitted fields are left untouched on
 * an existing row, or take repository-level defaults on a brand-new one. */
export interface ViewNodeUpsertRequest {
  functionId: FunctionId;
  visible?: boolean;
  collapsed?: boolean;
  color?: NodeColor | null;
  posX?: number;
  posY?: number;
  pinned?: boolean;
  originFunctionId?: FunctionId | null;
  originKind?: OriginKind;
  originImplied?: boolean;
}

export interface ViewNodesPatchRequest {
  upsert?: ViewNodeUpsertRequest[];
  remove?: FunctionId[];
}

/** The full post-state of every node in the view, so the client can
 * reconcile (TAD §4.3 #12). */
export interface ViewNodesPatchResponse {
  nodes: ViewNodeDto[];
}

/** `POST /binaries/{id}/last-view` request body (B16, I6). */
export interface SetLastViewRequest {
  viewId: ViewId;
}
/** One entry-point suggestion (E1b) for an empty canvas. */
export interface EntryPointDto {
  id: FunctionId;
  address: number;
  displayName: string;
  fanOut: number;
  fanIn: number;
}

export interface EntryPointsDto {
  entryPoints: EntryPointDto[];
}

/** One row in a `GET /binaries/{id}/functions` search result (B11/E1a) —
 * narrow, matching the `NeighbourRowDto` philosophy. */
export interface FunctionSearchRowDto {
  id: FunctionId;
  address: number;
  displayName: string;
  isRenamed: boolean;
  kind: FunctionKind;
  isUtility: boolean;
  fanIn: number;
  hasNotes: boolean;
  isEntryPoint: boolean;
}

export interface FunctionSearchPageDto {
  rows: FunctionSearchRowDto[];
  total: number;
  limit: number;
  offset: number;
  query: string | null;
}

/** Derived client-side from ViewNodeDto only — never from the edges table (D8b). */
export interface CanvasEdge {
  id: string;
  source: FunctionId;
  target: FunctionId;
  implied: boolean;
  kind: OriginKind;
}

export interface AdapterIdentityDto {
  ghidra: string;
  llm: string;
  llmModel: string;
}

/** F1a — single source of every threshold. Fetched once, staleTime: Infinity. */
export interface AppConfigDto {
  tableRowCap: number;
  callerSuppressThreshold: number;
  utilityFanInThreshold: number;
  fanOutAllHardCap: number;
  nodeCountSoftWarning: number;
  cardWidthPx: number;
  summaryConcurrency: number;
  // I6/D11/§2.5: ELK re-layout trigger threshold + animation duration. Not
  // in the TAD's original §3.4 sketch (its own prose names "8 px"/"400 ms"
  // but never lifts them into the config object) — added here so no
  // component hard-codes either literal (F1a).
  layoutHeightChangeThresholdPx: number;
  layoutAnimationMs: number;
  // I9: fast-scroll debounce guard for row-summary demand acquisition —
  // `hooks/useSummaryDemand.ts` reads this rather than hard-coding a value.
  summaryDemandDebounceMs: number;
  nodeColorPalette: NodeColor[];
  adapters: AdapterIdentityDto;
}

export interface LlmHealthDto {
  reachable: boolean;
  detail: string | null;
}

export interface HealthDto {
  status: string;
  dbOk: boolean;
  migrationRevision: string | null;
  ghidraAdapter: string;
  llmAdapter: string;
  // AM5: adapter reachability, so the UI can tell "no summaries because
  // misconfigured" from "no summaries yet".
  llmHealth: LlmHealthDto;
}

/** Machine-readable error codes (E4). */
export type ErrorCode =
  | "VALIDATION_ERROR"
  | "BINARY_NOT_FOUND"
  | "FUNCTION_NOT_FOUND"
  | "VIEW_NOT_FOUND"
  | "ADDRESS_UNRESOLVED"
  | "CONFIRMATION_MISMATCH"
  | "SUMMARY_ALREADY_PENDING"
  | "SUMMARY_PROVIDER_ERROR"
  | "SUMMARY_RATE_LIMITED"
  | "QUEUE_FULL"
  | "LAST_VIEW_DELETE_FORBIDDEN"
  | "GHIDRA_PROGRAM_MISMATCH"
  | "INTERNAL_ERROR";

export interface ErrorEnvelope {
  error: {
    code: ErrorCode;
    message: string;
    details?: Record<string, unknown> | null;
  };
}

// -- I7/I8: summary demand + queue -----------------------------------------

/** `POST /functions/{id}/summary` request body (endpoint 17). */
export interface SummaryDemandRequest {
  priority: Priority;
  reason?: string;
}

/** `POST /functions/{id}/summary` / `.../regenerate` response. */
export interface SummaryDemandResponseDto {
  functionId: FunctionId;
  summaryStatus: SummaryStatus;
  queuePosition: number | null;
  summaryShort: string | null;
}

export interface QueuedItemDto {
  functionId: FunctionId;
  displayName: string;
  priority: Priority;
}

export interface InFlightItemDto {
  functionId: FunctionId;
  displayName: string;
  startedAt: string | null;
}

/** `GET /queue` (endpoint 20) — the toolbar chip's data source. */
export interface QueueSnapshotDto {
  inFlight: InFlightItemDto[];
  queued: QueuedItemDto[];
  inFlightCount: number;
  queuedCount: number;
  pausedUntil: string | null;
}

export interface CancelPendingResponseDto {
  cancelledCount: number;
}

// -- I8: SSE events (`GET /events`, TAD §4.2 #22, E5/E5a/E5b) --------------

export interface SummaryEvent {
  type: "summary";
  functionId: FunctionId;
  summaryStatus: SummaryStatus;
  summaryShort: string | null;
  summaryModel: string | null;
  lowConfidence: boolean;
  generatedAt: string | null;
  errorCode: string | null;
  // C13 auto-display: the LLM-proposed name (null when the adapter/model
  // proposed none, or on error events). Drives the displayName patch on
  // every surface (E5a) so a reload is never needed to see it.
  nameLlm: string | null;
}

export interface QueueEvent {
  type: "queue";
  inFlightCount: number;
  queuedCount: number;
  pausedUntil: string | null;
  // Optional per-item detail: present on worker-driven events (pop/
  // complete transitions, published with the full GET /queue shape) and
  // absent on the older counter-only events from demand mutations. When
  // present the sidebar's live "thinking" panel updates instantly; when
  // absent the cached lists stay and only the counts refresh.
  inFlight?: InFlightItemDto[] | undefined;
  queued?: QueuedItemDto[] | undefined;
}

export interface BinaryEvent {
  type: "binary";
  binaryId: BinaryId;
  kind: "imported" | "deleted";
}

export interface ReconcileEvent {
  type: "reconcile";
}

export type ServerEvent = SummaryEvent | QueueEvent | BinaryEvent | ReconcileEvent;
