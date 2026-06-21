import { AnimatePresence, motion } from "framer-motion";
import { HardHat, Shirt, PersonStanding, MapPin, ShieldCheck, ShieldAlert } from "lucide-react";
import type { Detection } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATE: Record<string, { label: string; cls: string }> = {
  AUTHORIZED_ACCESS: { label: "Authorized", cls: "text-signal-green border-signal-green/40 bg-signal-green/10" },
  CLEAR: { label: "Clear", cls: "text-cyber-400 border-cyber-400/40 bg-cyber-400/10" },
  INTRUSION: { label: "Intrusion", cls: "text-signal-amber border-signal-amber/40 bg-signal-amber/10" },
  ZONE_VIOLATION: { label: "Zone Violation", cls: "text-signal-amber border-signal-amber/40 bg-signal-amber/10" },
  UNKNOWN_RFID: { label: "Unknown RFID", cls: "text-signal-amber border-signal-amber/40 bg-signal-amber/10" },
  UNAUTHORIZED_INTRUSION: { label: "Unauthorized", cls: "text-signal-red border-signal-red/40 bg-signal-red/10" },
};

function Tag({ ok, yes, no, icon: Icon }: { ok: boolean; yes: string; no: string; icon: typeof HardHat }) {
  return (
    <span className={cn("chip border", ok ? "border-signal-green/30 bg-signal-green/10 text-signal-green" : "border-signal-red/30 bg-signal-red/10 text-signal-red")}>
      <Icon className="h-3 w-3" /> {ok ? yes : no}
    </span>
  );
}

export function DetectionPanel({ detections }: { detections: Detection[] }) {
  return (
    <div className="space-y-2.5 overflow-y-auto pr-1">
      {detections.length === 0 && (
        <p className="py-8 text-center font-mono text-[11px] text-white/30">No active detections</p>
      )}
      <AnimatePresence initial={false}>
        {detections.map((d) => {
          const s = STATE[d.state] || STATE.CLEAR;
          return (
            <motion.div
              key={d.person_id}
              layout
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="glass p-3"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="grid h-7 w-7 place-items-center rounded-lg bg-cyber-500/20 font-display text-xs font-bold text-cyan-glow">
                    {d.person_id}
                  </span>
                  <div>
                    <p className="text-xs font-semibold text-white">Person {d.person_id}</p>
                    <p className="font-mono text-[10px] text-white/40">{d.name ?? "Unknown"} · {d.uid ?? "no-tag"}</p>
                  </div>
                </div>
                <span className={cn("chip border", s.cls)}>
                  {d.state.includes("AUTHOR") ? <ShieldCheck className="h-3 w-3" /> : <ShieldAlert className="h-3 w-3" />}
                  {s.label}
                </span>
              </div>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                <Tag ok={d.helmet} yes="Helmet" no="No Helmet" icon={HardHat} />
                <Tag ok={d.vest} yes="Vest" no="No Vest" icon={Shirt} />
                <span className="chip border border-white/15 bg-white/5 text-white/70">
                  <PersonStanding className="h-3 w-3" /> {d.posture}
                </span>
                <span className="chip border border-white/15 bg-white/5 text-white/70">
                  <MapPin className="h-3 w-3" /> {d.zone ?? "—"}
                </span>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-gradient-to-r from-cyber-500 to-cyan-glow" style={{ width: `${d.confidence * 100}%` }} />
                </div>
                <span className="font-mono text-[10px] text-white/50">{Math.round(d.confidence * 100)}%</span>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
