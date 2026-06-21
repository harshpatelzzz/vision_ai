import { useState } from "react";
import { Webcam, Cpu, Play, Pause, AlertTriangle } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { CameraStage, type CamSource } from "@/components/widgets/CameraStage";
import { DetectionPanel } from "@/components/widgets/DetectionPanel";
import { EventTimeline } from "@/components/widgets/EventTimeline";
import { useLiveFeed } from "@/hooks/useLiveFeed";
import { useHardwareStream } from "@/hooks/useApiData";
import { cn } from "@/lib/utils";

const SOURCES: { id: CamSource; label: string; icon: typeof Webcam }[] = [
  { id: "webcam", label: "Edge Webcam", icon: Webcam },
  { id: "esp32", label: "ESP32-CAM", icon: Cpu },
];

export default function LiveMonitoring() {
  const [source, setSource] = useState<CamSource>("webcam");
  const [running, setRunning] = useState(true);
  const stream = useHardwareStream();
  const { frame, wsStatus, error } = useLiveFeed(source, running, stream.data?.stream_url || undefined);

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        <GlassCard className="!p-3">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex gap-1.5 rounded-xl bg-black/30 p-1">
              {SOURCES.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSource(s.id)}
                  className={cn(
                    "flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition",
                    source === s.id ? "bg-cyan-glow/15 text-cyan-glow shadow-glow-sm" : "text-white/45 hover:text-white",
                  )}
                >
                  <s.icon className="h-3.5 w-3.5" /> {s.label}
                </button>
              ))}
            </div>
            <button
              onClick={() => setRunning((r) => !r)}
              className={cn(
                "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider",
                running ? "border-signal-red/40 bg-signal-red/10 text-signal-red" : "border-signal-green/40 bg-signal-green/10 text-signal-green",
              )}
            >
              {running ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
              {running ? "Stop" : "Start"}
            </button>
          </div>

          {error && (
            <div className="mb-3 flex items-center gap-2 rounded-lg border border-signal-amber/30 bg-signal-amber/10 px-3 py-2 text-xs text-signal-amber">
              <AlertTriangle className="h-4 w-4" /> {error}
            </div>
          )}

          <CameraStage source={source} frame={frame} running={running} />

          <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6">
            {[
              { k: "FPS", v: frame.fps },
              { k: "Latency", v: `${frame.latency_ms}ms` },
              { k: "Persons", v: frame.detections.length },
              { k: "Frame", v: frame.frame_index },
              { k: "Helmet-", v: frame.detections.filter((d) => !d.helmet).length },
              { k: "Intrusion", v: frame.detections.filter((d) => d.intrusion).length },
            ].map((s) => (
              <div key={s.k} className="rounded-lg border border-white/8 bg-white/[0.02] px-2 py-1.5 text-center">
                <p className="hud-label">{s.k}</p>
                <p className="font-display text-base font-bold text-white">{s.v}</p>
              </div>
            ))}
          </div>
          <p className="mt-2 text-center font-mono text-[10px] text-white/30">
            link {wsStatus} · boxes & IDs drawn by the live YOLOv8 + pose pipeline · one ID per tracked person
          </p>
        </GlassCard>

        <GlassCard>
          <SectionTitle>Event Timeline · Live</SectionTitle>
          <EventTimeline limit={20} dense />
        </GlassCard>
      </div>

      <GlassCard className="flex flex-col">
        <SectionTitle>AI Detection Panel</SectionTitle>
        <DetectionPanel detections={frame.detections} />
      </GlassCard>
    </div>
  );
}
