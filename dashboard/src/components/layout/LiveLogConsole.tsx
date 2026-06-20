import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Terminal, ChevronDown, Trash2, Pause, Play } from "lucide-react";
import { useSystem } from "@/store/SystemContext";
import { cn, fmtTime } from "@/lib/utils";
import type { LogLine } from "@/lib/types";

const SOURCE_COLOR: Record<LogLine["source"], string> = {
  YOLO: "text-cyber-400",
  BLOCKCHAIN: "text-signal-violet",
  RFID: "text-cyan-glow",
  ESP32: "text-emerald-400",
  HARDWARE: "text-signal-amber",
  TAMPER: "text-signal-red",
  VPAP: "text-sky-300",
  SYSTEM: "text-white/50",
};
const LEVEL_COLOR: Record<LogLine["level"], string> = {
  info: "text-white/70",
  success: "text-signal-green",
  warning: "text-signal-amber",
  critical: "text-signal-red",
};

export function LiveLogConsole() {
  const { logs, clearLogs } = useSystem();
  const [open, setOpen] = useState(true);
  const [paused, setPaused] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && !paused) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, open, paused]);

  return (
    <div className="panel z-20 rounded-tl-2xl">
      <div className="flex items-center gap-2 px-4 py-2">
        <Terminal className="h-4 w-4 text-cyan-glow" />
        <span className="font-display text-xs font-semibold uppercase tracking-[0.18em] text-white/80">
          Live Telemetry Console
        </span>
        <span className="rounded bg-white/8 px-1.5 py-0.5 font-mono text-[9px] text-white/50">
          {logs.length}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => setPaused((p) => !p)}
            className="rounded p-1.5 text-white/40 hover:bg-white/5 hover:text-white"
            title={paused ? "Resume autoscroll" : "Pause autoscroll"}
          >
            {paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
          </button>
          <button onClick={clearLogs} className="rounded p-1.5 text-white/40 hover:bg-white/5 hover:text-white">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setOpen((o) => !o)}
            className="rounded p-1.5 text-white/40 hover:bg-white/5 hover:text-white"
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform", !open && "rotate-180")} />
          </button>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 150 }}
            exit={{ height: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="h-[150px] overflow-y-auto bg-black/40 px-4 py-2 font-mono text-[11px] leading-relaxed">
              {logs.length === 0 && (
                <p className="py-6 text-center text-white/25">awaiting telemetry stream…</p>
              )}
              {logs.map((l) => (
                <div key={l.id} className="flex gap-2 whitespace-nowrap">
                  <span className="text-white/25">{fmtTime(l.ts)}</span>
                  <span className={cn("w-[84px] shrink-0 font-bold", SOURCE_COLOR[l.source])}>
                    [{l.source}]
                  </span>
                  <span className={cn("truncate", LEVEL_COLOR[l.level])}>{l.message}</span>
                </div>
              ))}
              <div ref={endRef} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
