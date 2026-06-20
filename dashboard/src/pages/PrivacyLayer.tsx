import { motion } from "framer-motion";
import { Camera, MemoryStick, Cpu, FileJson, Trash2, Boxes, EyeOff, ShieldCheck } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";

const STAGES = [
  { icon: Camera, label: "Camera", sub: "Frame captured", color: "#38bdf8" },
  { icon: MemoryStick, label: "Volatile RAM", sub: "No disk write", color: "#22d3ee" },
  { icon: Cpu, label: "YOLOv8 + Pose", sub: "On-device inference", color: "#a78bfa" },
  { icon: FileJson, label: "Metadata", sub: "bbox · ppe · posture", color: "#22e3a0" },
  { icon: Trash2, label: "Frame Deleted", sub: "Zeroized from RAM", color: "#ff4d61" },
  { icon: Boxes, label: "Blockchain", sub: "Signed metadata only", color: "#f5b73d" },
];

export default function PrivacyLayer() {
  return (
    <div className="space-y-4">
      <GlassCard reticle className="overflow-hidden">
        <div className="flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-xl bg-signal-green/15 ring-1 ring-signal-green/30">
            <EyeOff className="h-6 w-6 text-signal-green" />
          </div>
          <div>
            <h2 className="font-display text-xl font-bold text-white glow-text">PrivacyGuard Pipeline</h2>
            <p className="text-sm text-white/50">Raw frames never touch persistent storage — only signed metadata is retained.</p>
          </div>
          <div className="ml-auto hidden items-center gap-2 rounded-xl border border-signal-green/40 bg-signal-green/10 px-4 py-2.5 sm:flex">
            <ShieldCheck className="h-5 w-5 text-signal-green" />
            <span className="font-display text-sm font-bold tracking-wider text-signal-green">NO RAW VIDEO STORED</span>
          </div>
        </div>
      </GlassCard>

      <GlassCard>
        <SectionTitle>Data Flow</SectionTitle>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {STAGES.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.12 }}
              className="relative"
            >
              <div className="glass flex flex-col items-center gap-2 p-4 text-center">
                <div className="grid h-12 w-12 place-items-center rounded-xl" style={{ background: `${s.color}1a`, color: s.color }}>
                  <s.icon className="h-6 w-6" />
                </div>
                <p className="font-display text-xs font-bold text-white">{s.label}</p>
                <p className="font-mono text-[9px] text-white/40">{s.sub}</p>
              </div>
              {i < STAGES.length - 1 && (
                <motion.div
                  className="absolute -right-2 top-1/2 hidden h-0.5 w-4 -translate-y-1/2 bg-cyan-glow/40 lg:block"
                  animate={{ opacity: [0.2, 1, 0.2] }}
                  transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
                />
              )}
            </motion.div>
          ))}
        </div>
        <div className="relative mt-4 h-1 overflow-hidden rounded-full bg-white/5">
          <motion.div
            className="absolute h-full w-1/4 bg-gradient-to-r from-transparent via-cyan-glow to-transparent"
            animate={{ left: ["-25%", "100%"] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "linear" }}
          />
        </div>
      </GlassCard>

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { t: "Memory-Only Buffer", d: "VolatileFrameStore keeps ≤2 frames in RAM for live preview, then overwrites." },
          { t: "Metadata Extraction", d: "Only bbox, PPE flags, posture, intrusion & access decisions leave the frame." },
          { t: "Tamper Zeroization", d: "On tamper, logs + RAM are wiped; optional model deletion and shutdown." },
        ].map((c) => (
          <GlassCard key={c.t}>
            <p className="font-display text-sm font-semibold text-cyan-glow">{c.t}</p>
            <p className="mt-1 text-xs text-white/55">{c.d}</p>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
