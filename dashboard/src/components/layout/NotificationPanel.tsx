import { AnimatePresence, motion } from "framer-motion";
import { X, BellRing, CheckCheck, Trash2, AlertOctagon, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { useSystem } from "@/store/SystemContext";
import { cn, relativeTime } from "@/lib/utils";
import type { Severity } from "@/lib/types";

const ICON: Record<Severity, typeof Info> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  critical: AlertOctagon,
};
const COLOR: Record<Severity, string> = {
  info: "text-cyber-400 border-cyber-400/30",
  success: "text-signal-green border-signal-green/30",
  warning: "text-signal-amber border-signal-amber/30",
  critical: "text-signal-red border-signal-red/30",
};

export function NotificationPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { notifications, dismissNotification, markAllRead, clearNotifications } = useSystem();

  return (
    <AnimatePresence>
      {open && (
        <>
          <div className="fixed inset-0 z-40 bg-black/40" onClick={onClose} />
          <motion.aside
            initial={{ x: 360 }}
            animate={{ x: 0 }}
            exit={{ x: 360 }}
            transition={{ type: "spring", stiffness: 320, damping: 32 }}
            className="panel fixed right-0 top-0 z-50 flex h-full w-[340px] flex-col rounded-l-2xl"
          >
            <div className="flex items-center justify-between border-b border-white/8 px-4 py-4">
              <div className="flex items-center gap-2">
                <BellRing className="h-4 w-4 text-cyan-glow" />
                <h3 className="font-display text-sm font-semibold tracking-wide text-white">ALERTS</h3>
                <span className="rounded-full bg-white/10 px-2 py-0.5 font-mono text-[10px] text-white/60">
                  {notifications.length}
                </span>
              </div>
              <button onClick={onClose} className="rounded-lg p-1 text-white/40 hover:bg-white/5">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex items-center gap-2 border-b border-white/5 px-4 py-2">
              <button
                onClick={markAllRead}
                className="flex items-center gap-1 rounded-md px-2 py-1 font-mono text-[10px] text-white/50 hover:bg-white/5"
              >
                <CheckCheck className="h-3 w-3" /> Mark read
              </button>
              <button
                onClick={clearNotifications}
                className="flex items-center gap-1 rounded-md px-2 py-1 font-mono text-[10px] text-white/50 hover:bg-white/5"
              >
                <Trash2 className="h-3 w-3" /> Clear
              </button>
            </div>

            <div className="flex-1 space-y-2 overflow-y-auto p-3">
              {notifications.length === 0 && (
                <p className="py-10 text-center font-mono text-[11px] text-white/30">No active alerts</p>
              )}
              <AnimatePresence initial={false}>
                {notifications.map((n) => {
                  const Icon = ICON[n.severity];
                  return (
                    <motion.div
                      key={n.id}
                      layout
                      initial={{ opacity: 0, x: 30 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 30 }}
                      className={cn(
                        "group relative rounded-xl border bg-white/[0.03] p-3",
                        COLOR[n.severity],
                        !n.read && "ring-1 ring-inset ring-white/5",
                      )}
                    >
                      <div className="flex items-start gap-2">
                        <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-white">{n.title}</p>
                          <p className="mt-0.5 text-[11px] text-white/55">{n.message}</p>
                          <p className="mt-1 font-mono text-[9px] text-white/30">{relativeTime(n.ts)}</p>
                        </div>
                        <button
                          onClick={() => dismissNotification(n.id)}
                          className="text-white/30 opacity-0 transition hover:text-white group-hover:opacity-100"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
