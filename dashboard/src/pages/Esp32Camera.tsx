import { useState, useEffect } from "react";
import { Cpu, Link2, Wifi, Activity, RefreshCw, Play, Pause } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { StatusPill } from "@/components/ui/StatusPill";
import { CameraStage } from "@/components/widgets/CameraStage";
import { DetectionPanel } from "@/components/widgets/DetectionPanel";
import { useHardwareStream, useHardwareStatus, useHardwareSensors } from "@/hooks/useApiData";
import { useLiveFeed } from "@/hooks/useLiveFeed";
import { cn } from "@/lib/utils";

export default function Esp32Camera() {
  const stream = useHardwareStream();
  const status = useHardwareStatus();
  const sensors = useHardwareSensors();
  const [url, setUrl] = useState("");
  const [running, setRunning] = useState(false);
  const { frame, error } = useLiveFeed("esp32", running, url || undefined);

  useEffect(() => {
    if (stream.data?.stream_url) setUrl(stream.data.stream_url);
  }, [stream.data?.stream_url]);

  const online = status.data?.telemetry_registered || sensors.data?.connected;

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
      <div className="space-y-4">
        <GlassCard>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <SectionTitle>ESP32-CAM · Edge AI Stream</SectionTitle>
            <div className="flex items-center gap-2">
              <StatusPill severity={online ? "success" : "warning"} label={online ? "NODE LINKED" : "NO TELEMETRY"} />
              <button
                onClick={() => setRunning((r) => !r)}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 font-mono text-[11px] uppercase",
                  running ? "border-signal-red/40 bg-signal-red/10 text-signal-red" : "border-signal-green/40 bg-signal-green/10 text-signal-green",
                )}
              >
                {running ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                {running ? "Stop" : "Start"}
              </button>
            </div>
          </div>
          <div className="mb-3 flex gap-2">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="http://192.168.x.x:81/stream"
              className="flex-1 rounded-lg border border-white/10 bg-black/40 px-3 py-2 font-mono text-sm text-white outline-none placeholder:text-white/25 focus:border-cyan-glow/50"
            />
            <button onClick={() => stream.refetch()} className="flex items-center gap-1.5 rounded-lg border border-cyan-glow/40 bg-cyan-glow/10 px-3 text-cyan-glow">
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
          {error && <p className="mb-2 font-mono text-[11px] text-signal-amber">{error}</p>}
          <CameraStage source="esp32" frame={frame} running={running} />
          <p className="mt-2 font-mono text-[10px] text-white/30">
            The edge node ingests the ESP32-CAM MJPEG and runs YOLOv8 + pose + tripwire on it server-side.
          </p>
        </GlassCard>
      </div>

      <div className="space-y-4">
        <GlassCard>
          <SectionTitle>Node Telemetry</SectionTitle>
          <div className="space-y-2">
            <Stat icon={Cpu} label="Telemetry registered" value={String(status.data?.telemetry_registered ?? false)} />
            <Stat icon={Link2} label="Stream configured" value={String(status.data?.stream_url_configured ?? false)} />
            <Stat icon={Wifi} label="WiFi" value={sensors.data?.last?.wifi ? "UP" : "DOWN"} />
            <Stat icon={Activity} label="Sensors connected" value={String(sensors.data?.connected ?? false)} />
          </div>
          <p className="mt-3 rounded-lg border border-white/8 bg-black/20 p-2.5 font-mono text-[10px] text-white/45">
            {stream.data?.hint ?? "OpenCV captures MJPEG from this HTTP URL (ESP32-CAM)."}
          </p>
        </GlassCard>

        <GlassCard>
          <SectionTitle>AI Detections</SectionTitle>
          <DetectionPanel detections={frame.detections} />
        </GlassCard>
      </div>
    </div>
  );
}

function Stat({ icon: Icon, label, value }: { icon: typeof Cpu; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-white/8 bg-white/[0.02] px-3 py-2">
      <span className="flex items-center gap-2 font-mono text-[11px] text-white/50"><Icon className="h-3.5 w-3.5 text-cyber-400" /> {label}</span>
      <span className="font-mono text-xs font-bold text-white">{value}</span>
    </div>
  );
}
