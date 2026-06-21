import { useEffect, useRef, useState } from "react";
import { useWebSocket } from "./useWebSocket";
import { WS_PATHS, liveStart, liveStop } from "@/lib/api";
import type { FrameMeta } from "@/lib/types";

const EMPTY: FrameMeta = {
  frame_index: 0,
  fps: 0,
  latency_ms: 0,
  detections: [],
  simulated: false,
  running: false,
};

/**
 * Real live detection feed.
 *
 * Starts/stops the backend camera→YOLO→tracker service and subscribes to the
 * `/ws/live-events` channel, which streams the *currently tracked* persons —
 * one card per real person, persistent IDs, no mock data. When `running` is
 * false (or the component unmounts) the camera is released.
 */
export function useLiveFeed(source: "webcam" | "esp32", running: boolean, streamUrl?: string) {
  const [frame, setFrame] = useState<FrameMeta>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  // Start / stop the backend service when source or running changes.
  useEffect(() => {
    let cancelled = false;
    if (running) {
      liveStart(source, streamUrl)
        .then((s) => {
          if (!cancelled) {
            startedRef.current = true;
            setError(s.error ?? null);
          }
        })
        .catch((e) => !cancelled && setError(e?.message ?? "Failed to start live service"));
    }
    return () => {
      cancelled = true;
    };
  }, [source, running, streamUrl]);

  // Release the camera on unmount.
  useEffect(() => {
    return () => {
      if (startedRef.current) {
        liveStop().catch(() => undefined);
        startedRef.current = false;
      }
    };
  }, []);

  // Subscribe to the real detection stream.
  const { status } = useWebSocket<FrameMeta>({
    path: WS_PATHS.liveEvents,
    enabled: running,
    onMessage: (data) => {
      if (data && Array.isArray(data.detections)) setFrame(data);
    },
  });

  useEffect(() => {
    if (!running) setFrame(EMPTY);
  }, [running]);

  return { frame, wsStatus: status, error };
}
