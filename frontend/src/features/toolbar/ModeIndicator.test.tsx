/**
 * ADR 0006: the toolbar badge reflects `publicMode` from config.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModeIndicator } from "./ModeIndicator";

const configMock = vi.hoisted(() => ({ publicMode: false }));
vi.mock("@/config/ConfigProvider", () => ({
  useConfig: () => configMock,
}));

describe("ModeIndicator", () => {
  it("shows Private when publicMode is off", () => {
    configMock.publicMode = false;
    render(<ModeIndicator />);
    expect(screen.getByText(/Private/)).toBeInTheDocument();
  });

  it("shows Public when publicMode is on", () => {
    configMock.publicMode = true;
    render(<ModeIndicator />);
    expect(screen.getByText(/Public/)).toBeInTheDocument();
  });
});
