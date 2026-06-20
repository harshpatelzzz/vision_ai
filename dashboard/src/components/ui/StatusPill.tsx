import { cn } from "@/lib/utils";
import type { Severity } from "@/lib/types";

const MAP: Record<Severity, { dot: string; text: string; ring: string }> = {
  success: { dot: "bg-signal-green", text: "text-signal-green", ring: "border-signal-green/40 bg-signal-green/10" },
  info: { dot: "bg-cyber-400", text: "text-cyber-400", ring: "border-cyber-400/40 bg-cyber-400/10" },
  warning: { dot: "bg-signal-amber", text: "text-signal-amber", ring: "border-signal-amber/40 bg-signal-amber/10" },
  critical: { dot: "bg-signal-red", text: "text-signal-red", ring: "border-signal-red/40 bg-signal-red/10" },
};

export function StatusPill({
  severity = "info",
  label,
  pulse = true,
  className,
}: {
  severity?: Severity;
  label: string;
  pulse?: boolean;
  className?: string;
}) {
  const m = MAP[severity];
  return (
    <span className={cn("chip", m.ring, m.text, className)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", m.dot, pulse && "animate-pulse-glow")} />
      {label}
    </span>
  );
}

export function Dot({ severity = "info", className }: { severity?: Severity; className?: string }) {
  return <span className={cn("inline-block h-2 w-2 rounded-full", MAP[severity].dot, "animate-pulse-glow", className)} />;
}
