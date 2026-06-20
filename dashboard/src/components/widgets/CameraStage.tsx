import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { VideoOff, Camera } from "lucide-react";
import type { Detection, FrameMeta } from "@/lib/types";
import { cn } from "@/lib/utils";

export type CamSource = "webcam" | "esp32" | "demo";

const STATE_COLOR: Record<string, string> = {
  AUTHORIZED_ACCESS: "#22e3a0",
  CLEAR: "#38bdf8",
  INTRUSION: "#f5b73d",
  ZONE_VIOLATION: "#f5b73d",
  UNKNOWN_RFID: "#f5b73d",
  UNAUTHORIZED_INTRUSION: "#ff4d61",
};

// normalized tripwire polygon (matches config default region)
const TRIPWIRE: [number, number][] = [
  [0.16, 0.22],
  [0.84, 0.22],
  [0.84, 0.9],
  [0.16, 0.9],
];

function Overlay({ frame }: { frame: FrameMeta }) {
  return (
    <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
      {/* tripwire */}
      <polygon
        points={TRIPWIRE.map(([x, y]) => `${x * 1000},${y * 1000}`).join(" ")}
        fill="rgba(245,183,61,0.06)"
        stroke="rgba(245,183,61,0.6)"
        strokeWidth={2}
        strokeDasharray="8 6"
      />
      <text x={TRIPWIRE[0][0] * 1000 + 6} y={TRIPWIRE[0][1] * 1000 - 6} fill="#f5b73d" style={{ fontSize: 16, fontFamily: "JetBrains Mono" }}>
        TRIPWIRE · RESTRICTED
      </text>

      {frame.detections.map((d) => {
        const [x1, y1, x2, y2] = d.bbox;
        const color = STATE_COLOR[d.state] || "#38bdf8";
        const X = x1 * 1000, Y = y1 * 1000, W = (x2 - x1) * 1000, H = (y2 - y1) * 1000;
        return (
          <g key={d.person_id}>
            {/* skeleton */}
            {d.keypoints && (
              <g stroke={color} strokeWidth={1.5} opacity={0.85}>
                <line x1={d.keypoints[0][0] * 1000} y1={d.keypoints[0][1] * 1000} x2={(d.keypoints[1][0] + d.keypoints[2][0]) / 2 * 1000} y2={(d.keypoints[1][1] + d.keypoints[2][1]) / 2 * 1000} />
                <line x1={d.keypoints[1][0] * 1000} y1={d.keypoints[1][1] * 1000} x2={d.keypoints[2][0] * 1000} y2={d.keypoints[2][1] * 1000} />
                <line x1={d.keypoints[1][0] * 1000} y1={d.keypoints[1][1] * 1000} x2={d.keypoints[3][0] * 1000} y2={d.keypoints[3][1] * 1000} />
                <line x1={d.keypoints[2][0] * 1000} y1={d.keypoints[2][1] * 1000} x2={d.keypoints[4][0] * 1000} y2={d.keypoints[4][1] * 1000} />
                <line x1={d.keypoints[3][0] * 1000} y1={d.keypoints[3][1] * 1000} x2={d.keypoints[5][0] * 1000} y2={d.keypoints[5][1] * 1000} />
                <line x1={d.keypoints[4][0] * 1000} y1={d.keypoints[4][1] * 1000} x2={d.keypoints[6][0] * 1000} y2={d.keypoints[6][1] * 1000} />
                {d.keypoints.map((k, i) => (
                  <circle key={i} cx={k[0] * 1000} cy={k[1] * 1000} r={3} fill={color} stroke="none" />
                ))}
              </g>
            )}
            {/* bbox */}
            <rect x={X} y={Y} width={W} height={H} fill="none" stroke={color} strokeWidth={2.5} rx={4} />
            {/* corner ticks */}
            <path d={`M${X} ${Y + 16} L${X} ${Y} L${X + 16} ${Y}`} stroke={color} strokeWidth={3} fill="none" />
            <path d={`M${X + W - 16} ${Y + H} L${X + W} ${Y + H} L${X + W} ${Y + H - 16}`} stroke={color} strokeWidth={3} fill="none" />
            {/* label */}
            <rect x={X} y={Y - 34} width={Math.max(150, W)} height={30} fill="rgba(4,7,13,0.85)" stroke={color} strokeWidth={1} rx={3} />
            <text x={X + 6} y={Y - 13} fill="#fff" style={{ fontSize: 15, fontFamily: "JetBrains Mono" }}>
              ID{d.person_id} {d.helmet ? "H+" : "H-"} {d.vest ? "V+" : "V-"} · {d.posture} · {Math.round(d.confidence * 100)}%
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function CameraStage({
  source,
  streamUrl,
  frame,
}: {
  source: CamSource;
  streamUrl?: string;
  frame: FrameMeta;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [camError, setCamError] = useState<string | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;
    if (source === "webcam") {
      setCamError(null);
      navigator.mediaDevices
        ?.getUserMedia({ video: { width: 1280, height: 720 }, audio: false })
        .then((s) => {
          stream = s;
          if (videoRef.current) videoRef.current.srcObject = s;
        })
        .catch((e) => setCamError(e?.message || "Camera access denied"));
    }
    return () => stream?.getTracks().forEach((t) => t.stop());
  }, [source]);

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-xl border border-white/10 bg-black">
      {/* base layer */}
      {source === "webcam" && !camError && (
        <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-cover" />
      )}
      {source === "esp32" && streamUrl && (
        <img src={streamUrl} alt="ESP32-CAM" className="h-full w-full object-cover" />
      )}
      {(source === "demo" || (source === "esp32" && !streamUrl)) && (
        <div className="absolute inset-0 bg-grid">
          <div className="absolute inset-0 bg-gradient-to-br from-navy-800/40 to-black" />
          <motion.div
            className="absolute inset-x-0 h-12 bg-gradient-to-b from-cyan-glow/15 to-transparent"
            animate={{ top: ["-10%", "110%"] }}
            transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
          />
        </div>
      )}
      {source === "webcam" && camError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-grid text-center">
          <VideoOff className="h-10 w-10 text-signal-red" />
          <p className="font-display text-sm text-signal-red">Webcam Unavailable</p>
          <p className="max-w-xs font-mono text-[11px] text-white/45">{camError}. Switch to ESP32-CAM or demo feed.</p>
        </div>
      )}

      {/* detection overlay */}
      <Overlay frame={frame} />

      {/* scanline */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-x-0 h-px animate-scanline bg-cyan-glow/20" />
      </div>

      {/* HUD */}
      <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 rounded-lg bg-black/60 px-2.5 py-1.5 font-mono text-[11px] backdrop-blur">
        <Camera className="h-3.5 w-3.5 text-cyan-glow" />
        <span className="text-white/70">{source.toUpperCase()}</span>
        <span className="text-white/30">·</span>
        <span className="text-signal-green">{frame.fps} FPS</span>
        <span className="text-white/30">·</span>
        <span className="text-cyber-400">{frame.latency_ms}ms</span>
      </div>
      <div className="pointer-events-none absolute right-3 top-3 flex items-center gap-1.5 rounded-lg bg-black/60 px-2.5 py-1.5">
        <span className="h-2 w-2 animate-pulse-glow rounded-full bg-signal-red" />
        <span className="font-mono text-[10px] font-bold tracking-wider text-white/80">LIVE</span>
      </div>
      {frame.simulated && (
        <div className="pointer-events-none absolute bottom-3 left-3 rounded bg-signal-amber/15 px-2 py-1 font-mono text-[9px] uppercase tracking-widest text-signal-amber">
          Simulated detection feed · wire /ws/live-events for live AI
        </div>
      )}
      <div className={cn("pointer-events-none absolute bottom-3 right-3 rounded bg-black/60 px-2 py-1 font-mono text-[10px]", "text-white/60")}>
        {frame.detections.length} TGT · FRAME {frame.frame_index}
      </div>
    </div>
  );
}
