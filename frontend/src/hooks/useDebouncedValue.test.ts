import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDebouncedValue } from "./useDebouncedValue";

describe("useDebouncedValue", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebouncedValue("a", 250));
    expect(result.current).toBe("a");
  });

  it("only updates after the delay has elapsed", () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 250), {
      initialProps: { value: "a" },
    });

    rerender({ value: "b" });
    expect(result.current).toBe("a");

    act(() => {
      vi.advanceTimersByTime(249);
    });
    expect(result.current).toBe("a");

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe("b");
  });

  it("resets the timer on rapid successive changes", () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 250), {
      initialProps: { value: "a" },
    });

    rerender({ value: "b" });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    rerender({ value: "c" });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe("a");

    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(result.current).toBe("c");
  });
});
