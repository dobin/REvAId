/**
 * Anonymous per-browser view ownership (ADR 0006, `GRAPHREV_PUBLIC_MODE`).
 *
 * In public mode the server stays the authority for view *content* (B4:
 * positions/colors/visibility live in `view_nodes`), but "which views are
 * mine" becomes a browser-local fact: this module records, per binary, the
 * view ids this browser created or explicitly selected. Two anonymous
 * visitors therefore never land on the same view and cannot clobber each
 * other's canvas — the server never learns who owns what (no auth, B15
 * stays "Won't").
 *
 * Because the listing endpoint is closed in public mode (ADR 0006 v2), this
 * module is the *only* source of the picker's rows: it stores the name
 * alongside the id so the picker can render without a `GET /views` round
 * trip. The id itself is an unguessable random integer server-side, so the
 * id doubles as a capability (whoever holds it can fetch the view).
 *
 * Private instances never touch this module: `publicMode` is off, the
 * workspace defaults to the binary's first view, and `last_view_id` (B16)
 * keeps working as the shared resume pointer.
 *
 * The stored shape is versioned (`v`) so a future format change can migrate
 * in place instead of guessing at legacy entries.
 */
import type { BinaryId, ViewId } from "@/api/types";

const STORAGE_KEY = "graphrev.myViews.v2";

/** One owned view: the id (capability) plus a display name for the picker. */
export interface MyView {
  id: ViewId;
  name: string;
}

interface MyViewsStore {
  v: 2;
  /** binaryId -> views this browser owns, in selection order (latest last). */
  views: Record<string, MyView[]>;
}

/** Structural guard for a persisted view entry (defensive — the store is
 * untrusted JSON from localStorage, so its shape is not guaranteed). */
function isMyView(value: unknown): value is MyView {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { id?: unknown }).id === "number" &&
    typeof (value as { name?: unknown }).name === "string"
  );
}

function readStore(): MyViewsStore {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === null) return { v: 2, views: {} };
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      (parsed as { v?: unknown }).v !== 2 ||
      typeof (parsed as { views?: unknown }).views !== "object" ||
      (parsed as { views?: unknown }).views === null
    ) {
      return { v: 2, views: {} };
    }
    // Defensively keep only well-formed entries — a corrupt payload must
    // degrade to "no owned views", never crash the workspace. A single bad
    // entry drops just that entry, not the whole binary's list.
    const rawViews = (parsed as { views: Record<string, unknown> }).views;
    const views: Record<string, MyView[]> = {};
    for (const [key, entries] of Object.entries(rawViews)) {
      if (!Array.isArray(entries)) continue;
      const valid = entries.filter(isMyView);
      if (valid.length > 0) {
        views[key] = valid;
      }
    }
    return { v: 2, views };
  } catch {
    // localStorage unavailable (private browsing quirks) or unparsable —
    // public mode degrades to "create a fresh view each visit".
    return { v: 2, views: {} };
  }
}

function writeStore(store: MyViewsStore): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    // Quota exceeded / disabled storage: silently non-fatal, same rationale
    // as the read path.
  }
}

/** Views this browser owns for `binaryId`, in selection order. */
export function getMyViews(binaryId: BinaryId): MyView[] {
  return readStore().views[String(binaryId)] ?? [];
}

/** The most recently selected owned view for `binaryId`, or `null`. */
export function getLatestMyViewId(binaryId: BinaryId): ViewId | null {
  const views = getMyViews(binaryId);
  return views.length > 0 ? (views[views.length - 1] as MyView).id : null;
}

/** Records `viewId` as owned by this browser for `binaryId`, moving it to
 * the "latest" slot. Idempotent — re-recording an owned id only reorders
 * and refreshes the name. */
export function recordMyView(binaryId: BinaryId, viewId: ViewId, name: string): void {
  const store = readStore();
  const key = String(binaryId);
  const views = store.views[key] ?? [];
  const next = [...views.filter((v) => v.id !== viewId), { id: viewId, name }];
  store.views[key] = next;
  writeStore(store);
}

/** Drops `viewId` from this browser's owned set (the view still exists on
 * the server — deleting it is the caller's job via the CRUD endpoint). */
export function forgetMyView(binaryId: BinaryId, viewId: ViewId): void {
  const store = readStore();
  const binaryKey = String(binaryId);
  const views = store.views[binaryKey];
  if (!views) return;
  const next = views.filter((v) => v.id !== viewId);
  if (next.length === 0) {
    // Rest-spread omit (rather than `delete`) — keeps the key order stable
    // and satisfies the no-dynamic-delete lint rule.
    const rest = Object.fromEntries(
      Object.entries(store.views).filter(([key]) => key !== binaryKey),
    );
    store.views = rest;
  } else {
    store.views[binaryKey] = next;
  }
  writeStore(store);
}
