/**
 * Thin wrapper over `@radix-ui/react-dialog`, styled to match the app's
 * overlay house style (see BinaryPicker's Select.Content). The first Dialog
 * usage in the codebase (I12 import).
 */
import * as RadixDialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(0,0,0,0.35)",
  zIndex: 9998,
};

const contentStyle: React.CSSProperties = {
  position: "fixed",
  top: "50%",
  left: "50%",
  transform: "translate(-50%, -50%)",
  width: "min(32rem, calc(100vw - 2rem))",
  maxHeight: "calc(100vh - 4rem)",
  overflow: "auto",
  background: "#ffffff",
  border: "1px solid #e5e7eb",
  borderRadius: "0.5rem",
  boxShadow: "0 12px 32px rgba(0,0,0,0.18)",
  padding: "1.25rem",
  zIndex: 9999,
};

const titleStyle: React.CSSProperties = {
  margin: 0,
  marginBottom: "0.75rem",
  fontSize: "1rem",
  fontWeight: 600,
};

export function Dialog({
  open,
  onOpenChange,
  title,
  children,
  trigger,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
  trigger?: ReactNode;
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      {trigger ? <RadixDialog.Trigger asChild>{trigger}</RadixDialog.Trigger> : null}
      <RadixDialog.Portal>
        <RadixDialog.Overlay style={overlayStyle} />
        <RadixDialog.Content style={contentStyle} aria-describedby={undefined}>
          <RadixDialog.Title style={titleStyle}>{title}</RadixDialog.Title>
          {children}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
