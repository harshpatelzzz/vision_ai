import { cn } from "@/lib/utils";
import { AlertTriangle, Loader2, WifiOff, Inbox } from "lucide-react";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-white/[0.06]", className)} />;
}

export function LoadingState({ label = "Establishing uplink" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-cyber-400">
      <Loader2 className="h-7 w-7 animate-spin" />
      <p className="font-mono text-xs uppercase tracking-widest text-white/50">{label}…</p>
    </div>
  );
}

export function ErrorState({
  title = "Link interrupted",
  message = "The edge node is unreachable. Retrying automatically.",
}: {
  title?: string;
  message?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-signal-red/25 bg-signal-red/5 py-10 text-center">
      <WifiOff className="h-8 w-8 text-signal-red" />
      <p className="font-display text-sm font-semibold text-signal-red">{title}</p>
      <p className="max-w-xs font-mono text-[11px] text-white/45">{message}</p>
    </div>
  );
}

export function EmptyState({ label = "No data yet" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-white/30">
      <Inbox className="h-7 w-7" />
      <p className="font-mono text-[11px] uppercase tracking-widest">{label}</p>
    </div>
  );
}

export function WarningBanner({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-signal-amber/30 bg-signal-amber/10 px-3 py-2 text-xs text-signal-amber">
      <AlertTriangle className="h-4 w-4 shrink-0" />
      {children}
    </div>
  );
}
