import { useState } from "react";
import { Webcam, Cpu, MonitorPlay, Play, Pause } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { CameraStage, type CamSource } from "@/components/widgets/CameraStage";
import { DetectionPanel } from "@/components/widgets/DetectionPanel";
import { EventTimeline } from "@/components/widgets/EventTimeline";
import { useLiveDetections } from "@/hooks/useLiveDetections";
import { useHardwareStream } from "@/hooks/useApiData";
import { cn } from "@/lib/utils";

const SOURCES: { id: CamSource; label: string; icon: typeof Webcam }[] = [
  { id: "webcam", label: "Webcam", icon: Webcam },
  { id: "esp32", label: "ESP32-CAM", icon: Cpu },
  { id: "demo", label: "Demo Feed", icon: MonitorPlay },
];

export default function LiveMonitoring() {
  const [source, setSource] = useState<CamSource>("demo");
  const [running, setRunning] = useState(true);
  const frame = useLiveDetections(running);
  const stream = useHardwareStream();

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
              {running ? "Pause" : "Resume"}
            </button>
          </div>

          <CameraStage source={source} streamUrl={stream.data?.stream_url || undefined} frame={frame} />

          <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6">
            {[
              { k: "FPS", v: frame.fps },
              { k: "Latency", v: `${frame.latency_ms}ms` },
              { k: "Targets", v: frame.detections.length },
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
