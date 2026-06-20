import { motion, AnimatePresence } from "framer-motion";
import {
  HardHat, Shirt, Crosshair, ShieldAlert, UserCheck, UserX, ScanLine, Cpu, CheckCircle2,
} from "lucide-react";
import { useBlockchain } from "@/hooks/useApiData";
import { cn, eventLabel, fmtTime, severityForEvent, shortHash } from "@/lib/utils";
import { EmptyState } from "@/components/ui/States";
import type { Block, Severity } from "@/lib/types";

const ICON: Record<string, typeof HardHat> = {
  NO_HELMET: HardHat,
  NO_VEST: Shirt,
  INTRUSION: Crosshair,
  TAMPER_DETECTED: ShieldAlert,
  AUTHORIZED_ACCESS: UserCheck,
  UNAUTHORIZED_INTRUSION: UserX,
  ZONE_VIOLATION: UserX,
  UNKNOWN_RFID: ScanLine,
  ACCESS_DENIED: UserX,
  GENESIS: Cpu,
};

const SEV_COLOR: Record<Severity, string> = {
  success: "text-signal-green border-signal-green/30 bg-signal-green/5",
  info: "text-cyber-400 border-cyber-400/30 bg-cyber-400/5",
  warning: "text-signal-amber border-signal-amber/30 bg-signal-amber/5",
  critical: "text-signal-red border-signal-red/30 bg-signal-red/5",
};

export function EventTimeline({ limit = 40, dense = false }: { limit?: number; dense?: boolean }) {
  const { data } = useBlockchain();
  const blocks: Block[] = data ? [...data.chain].reverse().slice(0, limit) : [];

  return (
    <div className={cn("relative space-y-2 overflow-y-auto pr-1", dense ? "max-h-[260px]" : "max-h-[520px]")}>
      {blocks.length === 0 && <EmptyState label="No events logged" />}
      <AnimatePresence initial={false}>
        {blocks.map((b) => {
          const type = b.event?.alert_type || b.event?.type || "EVENT";
          const sev = type === "GENESIS" ? "info" : severityForEvent(type);
          const Icon = ICON[type] || CheckCircle2;
          const zone = b.event?.access?.zone;
          const name = b.event?.access?.name;
          return (
            <motion.div
              key={`${b.index}-${b.hash}`}
              layout
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              className={cn("flex items-start gap-3 rounded-xl border p-2.5", SEV_COLOR[sev])}
            >
              <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-black/30">
                <Icon className="h-3.5 w-3.5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-xs font-semibold text-white">{eventLabel(type)}</p>
                  <span className="shrink-0 font-mono text-[9px] text-white/35">{fmtTime(b.timestamp)}</span>
                </div>
                <p className="mt-0.5 truncate font-mono text-[10px] text-white/45">
                  blk#{b.index} · {shortHash(b.hash, 6, 4)}
                  {zone ? ` · ${zone}` : ""}
                  {name ? ` · ${name}` : ""}
                </p>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
