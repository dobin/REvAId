import "@testing-library/jest-dom/vitest";

// jsdom has no layout engine: ResizeObserver does not exist, and every
// element reports zero size. `@xyflow/react` needs a ResizeObserver, and
// `@tanstack/react-virtual` needs a non-zero scroll-container height to
// compute which rows are "visible" — without these, virtualized lists and
// the canvas render as empty in tests even though they work in a real
// browser. Both are test-environment shims only; no application code
// depends on them.
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

interface GlobalWithResizeObserver {
  ResizeObserver?: typeof MockResizeObserver;
}

(globalThis as GlobalWithResizeObserver).ResizeObserver ??= MockResizeObserver;

Object.defineProperty(HTMLElement.prototype, "clientHeight", {
  configurable: true,
  value: 320,
});
Object.defineProperty(HTMLElement.prototype, "clientWidth", {
  configurable: true,
  value: 380,
});
Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
  configurable: true,
  value: 320,
});
Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
  configurable: true,
  value: 380,
});
