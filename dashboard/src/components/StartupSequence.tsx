import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ShieldCheck } from "lucide-react";

const STEPS = [
  "INITIALIZING EDGE KERNEL",
  "LOADING YOLOv8 PPE + POSE MODELS",
  "ARMING TRIPWIRE ZONES",
  "ENGAGING PRIVACYGUARD · MEMORY-ONLY",
  "SYNCING BLOCKCHAIN LEDGER",
  "VERIFYING MERKLE ROOTS",
  "LINKING ESP32 TELEMETRY BUS",
  "C2 UPLINK ESTABLISHED",
];

export function StartupSequence({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (step >= STEPS.length) {
      const t = setTimeout(() => {
        setDone(true);
        setTimeout(onDone, 650);
      }, 350);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setStep((s) => s + 1), 230);
    return () => clearTimeout(t);
  }, [step, onDone]);

  return (
    <AnimatePresence>
      {!done && (
        <motion.div
          exit={{ opacity: 0, scale: 1.04 }}
          transition={{ duration: 0.6 }}
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-void bg-grid"
        >
          <div className="pointer-events-none absolute inset-0 bg-radial-glow" />
          <motion.div
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="relative mb-8"
          >
            <div className="grid h-24 w-24 place-items-center rounded-3xl bg-gradient-to-br from-cyber-500/30 to-cyan-glow/20 ring-1 ring-cyan-glow/40">
              <ShieldCheck className="h-12 w-12 text-cyan-glow" />
            </div>
            <span className="absolute inset-0 animate-pulse-glow rounded-3xl ring-2 ring-cyan-glow/30" />
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="font-display text-2xl font-bold tracking-[0.3em] text-white glow-text"
          >
            POSEVISION
          </motion.h1>
          <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.4em] text-cyber-400/80">
            Edge AI Command &amp; Control
          </p>

          <div className="mt-10 h-44 w-[340px] max-w-[80vw] font-mono text-[11px]">
            {STEPS.slice(0, step).map((s, i) => (
              <motion.div
                key={s}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex items-center gap-2 text-white/60"
              >
                <span className="text-signal-green">✓</span>
                <span>{s}</span>
              </motion.div>
            ))}
            {step < STEPS.length && (
              <div className="flex items-center gap-2 text-cyan-glow">
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-cyan-glow border-t-transparent" />
                <span>{STEPS[step]}</span>
              </div>
            )}
          </div>

          <div className="mt-4 h-1 w-[340px] max-w-[80vw] overflow-hidden rounded-full bg-white/5">
            <motion.div
              className="h-full bg-gradient-to-r from-cyber-500 to-cyan-glow shadow-glow"
              animate={{ width: `${(step / STEPS.length) * 100}%` }}
              transition={{ ease: "easeOut" }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
