import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Severity } from "@/lib/types";

const ACCENT: Record<Severity, string> = {
  success: "text-signal-green",
  info: "text-cyber-400",
  warning: "text-signal-amber",
  critical: "text-signal-red",
};
const GLOW: Record<Severity, string> = {
  success: "from-signal-green/20",
  info: "from-cyber-400/20",
  warning: "from-signal-amber/20",
  critical: "from-signal-red/25",
};

export function StatCard({
  label,
  value,
  icon: Icon,
  severity = "info",
  hint,
  trend,
  loading,
}: {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  severity?: Severity;
  hint?: string;
  trend?: string;
  loading?: boolean;
}) {
  return (
    <motion.div
      whileHover={{ y: -3 }}
      transition={{ type: "spring", stiffness: 300, damping: 22 }}
      className="glass relative overflow-hidden p-4"
    >
      <div className={cn("pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-gradient-to-br to-transparent blur-2xl", GLOW[severity])} />
      <div className="flex items-start justify-between">
        <span className="hud-label">{label}</span>
        {Icon && <Icon className={cn("h-4 w-4", ACCENT[severity])} />}
      </div>
      <div className="mt-3 flex items-end gap-2">
        {loading ? (
          <div className="h-8 w-16 animate-pulse rounded bg-white/10" />
        ) : (
          <span className={cn("stat-value glow-text", ACCENT[severity])}>{value}</span>
        )}
        {trend && <span className="mb-1 font-mono text-[11px] text-white/40">{trend}</span>}
      </div>
      {hint && <p className="mt-1 font-mono text-[10px] text-white/35">{hint}</p>}
    </motion.div>
  );
}
