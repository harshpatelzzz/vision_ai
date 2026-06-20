import { motion } from "framer-motion";

const NODES = [
  { x: 120, y: 90, label: "EDGE-01", active: true },
  { x: 300, y: 60, label: "ESP32-CAM", active: true },
  { x: 470, y: 120, label: "RFID-GATE", active: true },
  { x: 250, y: 190, label: "SENSOR-BUS", active: true },
  { x: 420, y: 220, label: "LEDGER", active: true },
];
const HUB = { x: 300, y: 150 };

export function EdgeNodeMap() {
  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl">
      <svg viewBox="0 0 600 300" className="h-full w-full">
        {/* concentric radar rings */}
        {[60, 110, 160].map((r) => (
          <circle key={r} cx={HUB.x} cy={HUB.y} r={r} fill="none" stroke="rgba(34,211,238,0.08)" />
        ))}
        {/* sweeping radar */}
        <motion.line
          x1={HUB.x}
          y1={HUB.y}
          x2={HUB.x + 160}
          y2={HUB.y}
          stroke="rgba(34,211,238,0.35)"
          strokeWidth={1.5}
          style={{ originX: `${HUB.x}px`, originY: `${HUB.y}px` }}
          animate={{ rotate: 360 }}
          transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
        />
        {/* links */}
        {NODES.map((n) => (
          <line key={`l-${n.label}`} x1={HUB.x} y1={HUB.y} x2={n.x} y2={n.y} stroke="rgba(34,211,238,0.18)" strokeDasharray="3 4" />
        ))}
        {/* data pulses */}
        {NODES.map((n, i) => (
          <motion.circle
            key={`p-${n.label}`}
            r={2.5}
            fill="#22d3ee"
            initial={{ cx: HUB.x, cy: HUB.y, opacity: 0 }}
            animate={{ cx: [HUB.x, n.x], cy: [HUB.y, n.y], opacity: [0, 1, 0] }}
            transition={{ duration: 2.2, repeat: Infinity, delay: i * 0.4, ease: "easeInOut" }}
          />
        ))}
        {/* hub */}
        <circle cx={HUB.x} cy={HUB.y} r={8} fill="#1e90ff" />
        <circle cx={HUB.x} cy={HUB.y} r={8} fill="none" stroke="#22d3ee" className="animate-pulse-glow" />
        {/* nodes */}
        {NODES.map((n) => (
          <g key={n.label}>
            <circle cx={n.x} cy={n.y} r={5} fill="#070d1c" stroke="#22e3a0" strokeWidth={1.5} />
            <circle cx={n.x} cy={n.y} r={5} fill="#22e3a0" opacity={0.25} className="animate-pulse-glow" />
            <text x={n.x + 9} y={n.y + 3} className="fill-white/55" style={{ fontSize: 8, fontFamily: "JetBrains Mono" }}>
              {n.label}
            </text>
          </g>
        ))}
      </svg>
      <div className="pointer-events-none absolute left-3 top-3 font-mono text-[9px] uppercase tracking-[0.3em] text-cyber-400/70">
        Edge Mesh · Live
      </div>
    </div>
  );
}
