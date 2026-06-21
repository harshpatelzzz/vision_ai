import { useEffect, useRef, useState } from "react";
import { VideoOff, Camera } from "lucide-react";
import { VIDEO_STREAM_URL } from "@/lib/api";
import type { FrameMeta } from "@/lib/types";

export type CamSource = "webcam" | "esp32";

/**
 * Live camera stage. The frame shown is the **real** annotated MJPEG produced by
 * the backend YOLO + pose + tripwire pipeline (`/video/stream`) — bounding boxes,
 * skeletons and persistent track IDs are drawn server-side, so what you see is
 * exactly what the AI detected. The HUD + target count come from the live
 * WebSocket detections. Nothing is simulated.
 */
export function CameraStage({ source, frame, running }: { source: CamSource; frame: FrameMeta; running: boolean }) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [imgError, setImgError] = useState(false);
  // cache-bust so the MJPEG reconnects cleanly on (re)start
  const [streamKey, setStreamKey] = useState(0);

  useEffect(() => {
    setImgError(false);
    setStreamKey((k) => k + 1);
  }, [source, running]);

  const streamSrc = `${VIDEO_STREAM_URL}?s=${source}&k=${streamKey}`;

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-xl border border-white/10 bg-black">
      {running && !imgError ? (
        <img
          ref={imgRef}
          src={streamSrc}
          alt="Live annotated feed"
          className="h-full w-full object-contain"
          onError={() => setImgError(true)}
        />
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-grid text-center">
          {imgError ? <VideoOff className="h-10 w-10 text-signal-red" /> : <Camera className="h-10 w-10 text-white/30" />}
          <p className="font-display text-sm text-white/60">
            {imgError ? "Camera Unavailable" : "Feed Paused"}
          </p>
          <p className="max-w-xs font-mono text-[11px] text-white/40">
            {imgError
              ? "Could not open the edge camera. Ensure it is free (close other apps) and the backend is running."
              : "Press Resume to start the edge AI camera pipeline."}
          </p>
        </div>
      )}

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
        <span className={`h-2 w-2 rounded-full ${running && !imgError ? "animate-pulse-glow bg-signal-red" : "bg-white/30"}`} />
        <span className="font-mono text-[10px] font-bold tracking-wider text-white/80">{running && !imgError ? "LIVE" : "OFF"}</span>
      </div>
      <div className="pointer-events-none absolute bottom-3 right-3 rounded bg-black/60 px-2 py-1 font-mono text-[10px] text-white/60">
        {frame.detections.length} TGT · FRAME {frame.frame_index}
      </div>
    </div>
  );
}
