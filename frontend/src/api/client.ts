/**
 * Typed fetch wrapper. Unwraps the E4 error envelope into an {@link ApiError}
 * so callers can branch on `error.code` rather than parsing response bodies
 * themselves.
 */
import type { ErrorEnvelope } from "./types";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown> | null;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const API_BASE = "/api/v1";

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as { error?: unknown }).error === "object"
  );
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // no JSON body — fall through to a generic error below
    }
    if (isErrorEnvelope(body)) {
      throw new ApiError(response.status, body.error.code, body.error.message, body.error.details);
    }
    throw new ApiError(response.status, "INTERNAL_ERROR", `Request to ${path} failed.`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function jsonInit(method: string, body?: unknown): RequestInit {
  return body === undefined ? { method } : { method, body: JSON.stringify(body) };
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) => request<T>(path, jsonInit("POST", body)),
  patch: <T>(path: string, body?: unknown) => request<T>(path, jsonInit("PATCH", body)),
  delete: <T>(path: string, params?: Record<string, string>) => {
    const suffix = params ? `?${new URLSearchParams(params).toString()}` : "";
    return request<T>(`${path}${suffix}`, { method: "DELETE" });
  },
};
