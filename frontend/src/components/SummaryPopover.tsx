/**
 * Thin wrapper over `@radix-ui/react-popover`, styled to match the app's
 * overlay house style (mirrors `Dialog.tsx` / the neighbour-row hover
 * tooltip). Used by `CardSummary` to turn the card's one-line summary into a
 * hover-open floating panel that shows the full `short` + `long` text
 * (§4.3 card affordances).
 *
 * A card summary is a *wall of small clamped text* inline; on the canvas the
 * card also sits inside React Flow's `overflow: hidden` wrapper. A portalled
 * Radix Tooltip escapes the clipping/z-index war while revealing the full
 * text on hover (and keyboard focus).
 *
 * The trigger is rendered `asChild` so the caller owns the trigger element
 * (and can `stopPropagation` on it so opening the popover doesn't also select
 * the card / open the detail panel). Controlled `open`/`onOpenChange` so the
 * caller can also close it after an in-popover action if needed.
 */
import * as RadixTooltip from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

const POPOVER_WIDTH_PX = 416; // 26rem @ 16px base — matches FunctionInfoTooltip.

const contentStyle: React.CSSProperties = {
  zIndex: 9999,
  width: POPOVER_WIDTH_PX,
  maxWidth: "calc(100vw - 2rem)",
  maxHeight: "60vh",
  overflowY: "auto",
  padding: "0.75rem",
  background: "#ffffff",
  border: "1px solid #d1d5db",
  borderRadius: "0.375rem",
  boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
  fontSize: "0.8125rem",
  lineHeight: 1.5,
  color: "#374151",
  whiteSpace: "normal",
  textAlign: "left",
};

const arrowStyle: React.CSSProperties = {
  fill: "#ffffff",
};

export function SummaryPopover({
  open,
  onOpenChange,
  trigger,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trigger: ReactNode;
  children: ReactNode;
}) {
  return (
    <RadixTooltip.Provider delayDuration={0} skipDelayDuration={0}>
      <RadixTooltip.Root open={open} onOpenChange={onOpenChange}>
        <RadixTooltip.Trigger asChild>{trigger}</RadixTooltip.Trigger>
        <RadixTooltip.Portal>
          <RadixTooltip.Content
          side="top"
          align="start"
          sideOffset={6}
          collisionPadding={8}
          style={contentStyle}
          >
            {children}
            <RadixTooltip.Arrow style={arrowStyle} />
          </RadixTooltip.Content>
        </RadixTooltip.Portal>
      </RadixTooltip.Root>
    </RadixTooltip.Provider>
  );
}
