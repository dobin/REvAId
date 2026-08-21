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
export type OriginKind = "root" | "fanout" | "callstack";
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
  functionCount: number;
  edgeCount: number;
  lastViewId: ViewId | null;
  createdAt: string;
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
  displayName: string; // name_analyst ?? name_ghidra (B6)
  nameGhidra: string;
  nameAnalyst: string | null;
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
  nodeColorPalette: NodeColor[];
  adapters: AdapterIdentityDto;
}

export interface HealthDto {
  status: string;
  dbOk: boolean;
  migrationRevision: string | null;
  ghidraAdapter: string;
  llmAdapter: string;
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
  | "INTERNAL_ERROR";

export interface ErrorEnvelope {
  error: {
    code: ErrorCode;
    message: string;
    details?: Record<string, unknown> | null;
  };
}
