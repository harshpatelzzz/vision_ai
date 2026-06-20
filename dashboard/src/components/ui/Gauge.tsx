import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { clamp } from "@/lib/utils";
import type { Severity } from "@/lib/types";

const STROKE: Record<Severity, string> = {
  success: "#22e3a0",
  info: "#38bdf8",
  warning: "#f5b73d",
  critical: "#ff4d61",
};

/** Radial gauge (270° sweep) for sensor values. */
export function Gauge({
  value,
  min = 0,
  max = 100,
  unit = "",
  label,
  severity = "info",
  size = 132,
}: {
  value: number | undefined;
  min?: number;
  max?: number;
  unit?: string;
  label: string;
  severity?: Severity;
  size?: number;
}) {
  const has = value != null && !Number.isNaN(value);
  const v = has ? clamp(value as number, min, max) : min;
  const pct = (v - min) / (max - min || 1);
  const sweep = 0.75; // 270deg
  const r = size / 2 - 12;
  const c = 2 * Math.PI * r;
  const dash = c * sweep;
  const offset = dash * (1 - pct);
  const color = STROKE[severity];

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="rotate-[135deg]">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth={9}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${c}`}
          />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={9}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${c}`}
            initial={{ strokeDashoffset: dash }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            style={{ filter: `drop-shadow(0 0 6px ${color})` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn("font-display text-2xl font-bold tabular-nums")} style={{ color }}>
            {has ? (Number.isInteger(v) ? v : v.toFixed(1)) : "—"}
          </span>
          <span className="font-mono text-[10px] text-white/40">{unit}</span>
        </div>
      </div>
      <span className="hud-label mt-1">{label}</span>
    </div>
  );
}
