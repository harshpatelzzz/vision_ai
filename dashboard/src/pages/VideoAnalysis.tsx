import { useRef, useState } from "react";
import { Upload, Film, Play, Terminal } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { DetectionPanel } from "@/components/widgets/DetectionPanel";
import { useLiveDetections } from "@/hooks/useLiveDetections";

export default function VideoAnalysis() {
  const [src, setSrc] = useState<string | null>(null);
  const [name, setName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const frame = useLiveDetections(Boolean(src));

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setName(f.name);
    setSrc(URL.createObjectURL(f));
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
      <GlassCard>
        <SectionTitle>Recorded Video Analysis</SectionTitle>
        <input ref={inputRef} type="file" accept="video/*" onChange={onFile} className="hidden" />
        {!src ? (
          <button
            onClick={() => inputRef.current?.click()}
            className="flex aspect-video w-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-white/15 bg-grid text-white/50 transition hover:border-cyan-glow/40 hover:text-cyan-glow"
          >
            <Upload className="h-10 w-10" />
            <p className="font-display text-sm">Drop or select a video file</p>
            <p className="font-mono text-[10px] text-white/35">MP4 / WebM · analyzed in-browser with overlay</p>
          </button>
        ) : (
          <div className="relative aspect-video w-full overflow-hidden rounded-xl border border-white/10 bg-black">
            <video src={src} autoPlay loop controls className="h-full w-full object-contain" />
            <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 rounded-lg bg-black/60 px-2.5 py-1.5 font-mono text-[11px]">
              <Film className="h-3.5 w-3.5 text-cyan-glow" /> {name} · {frame.fps} FPS
            </div>
          </div>
        )}
        <div className="mt-3 flex items-center gap-2">
          <button onClick={() => inputRef.current?.click()} className="flex items-center gap-1.5 rounded-lg border border-cyan-glow/40 bg-cyan-glow/10 px-3 py-2 font-mono text-xs uppercase tracking-wider text-cyan-glow">
            <Play className="h-3.5 w-3.5" /> Load File
          </button>
          <p className="font-mono text-[10px] text-white/40">
            Server-side batch analysis: <span className="text-cyber-400">python scripts/video_pipeline.py</span>
          </p>
        </div>
      </GlassCard>

      <GlassCard>
        <SectionTitle><span className="flex items-center gap-2"><Terminal className="h-3.5 w-3.5" /> Detections</span></SectionTitle>
        <DetectionPanel detections={src ? frame.detections : []} />
      </GlassCard>
    </div>
  );
}
