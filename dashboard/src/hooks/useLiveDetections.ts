import { useEffect, useRef, useState } from "react";
import type { Detection, DetectionState, FrameMeta } from "@/lib/types";

/*
 * Live detection feed.
 *
 * The backend's /ws/live-events channel is currently a reserved placeholder
 * (api/server.py notes: "Wire EventEngine.recent_events here"). Until the edge
 * pipeline publishes per-frame detections, this hook generates a realistic,
 * clearly-labelled SIMULATED overlay so the command center is fully demonstrable.
 * When the backend starts emitting frames on that channel, swap the simulator
 * for the useWebSocket("/ws/live-events") payload — the Detection shape matches
 * the normalized event schema (ppe, posture, intrusion, access).
 */

const ZONES = ["ZoneA", "ZoneB", "ZoneC"];
const NAMES = ["S. Rao", "M. Khan", "A. Verma", "Unknown", "J. Lee"];

function rand(a: number, b: number) {
  return a + Math.random() * (b - a);
}

function makeDetection(id: number): Detection {
  const helmet = Math.random() > 0.32;
  const vest = Math.random() > 0.4;
  const intrusion = Math.random() > 0.55;
  const known = Math.random() > 0.25;
  const zone = ZONES[Math.floor(Math.random() * ZONES.length)];
  const w = rand(0.1, 0.18);
  const h = rand(0.28, 0.42);
  const x = rand(0.05, 0.95 - w);
  const y = rand(0.1, 0.95 - h);

  let state: DetectionState = "CLEAR";
  if (intrusion) {
    if (!known) state = Math.random() > 0.5 ? "UNKNOWN_RFID" : "UNAUTHORIZED_INTRUSION";
    else state = zone === "ZoneC" ? "ZONE_VIOLATION" : "AUTHORIZED_ACCESS";
  }

  // crude skeleton: head, shoulders, hips, knees within bbox (normalized)
  const cx = x + w / 2;
  const keypoints: [number, number][] = [
    [cx, y + h * 0.12],
    [x + w * 0.3, y + h * 0.32],
    [x + w * 0.7, y + h * 0.32],
    [x + w * 0.35, y + h * 0.6],
    [x + w * 0.65, y + h * 0.6],
    [x + w * 0.4, y + h * 0.95],
    [x + w * 0.6, y + h * 0.95],
  ];

  return {
    person_id: id,
    bbox: [x, y, x + w, y + h],
    helmet,
    vest,
    posture: Math.random() > 0.85 ? "Lying" : Math.random() > 0.5 ? "Sitting" : "Standing",
    intrusion,
    zone,
    uid: known ? `A1:B2:C3:0${id}` : null,
    name: known ? NAMES[id % NAMES.length] : "Unknown",
    state,
    confidence: rand(0.71, 0.98),
    keypoints,
  };
}

export function useLiveDetections(running: boolean) {
  const [frame, setFrame] = useState<FrameMeta>({
    frame_index: 0,
    fps: 0,
    latency_ms: 0,
    detections: [],
    simulated: true,
  });
  const idx = useRef(0);
  const persons = useRef<Detection[]>([makeDetection(1), makeDetection(2)]);

  useEffect(() => {
    if (!running) return;
    const tick = window.setInterval(() => {
      idx.current += 1;
      // occasionally change population (1..3 people)
      if (idx.current % 24 === 0) {
        const count = 1 + Math.floor(Math.random() * 3);
        persons.current = Array.from({ length: count }, (_, i) => makeDetection(i + 1));
      } else {
        // jitter bboxes to feel alive
        persons.current = persons.current.map((d) => {
          const dx = rand(-0.012, 0.012);
          const dy = rand(-0.01, 0.01);
          const nb: [number, number, number, number] = [
            Math.max(0, d.bbox[0] + dx),
            Math.max(0, d.bbox[1] + dy),
            Math.min(1, d.bbox[2] + dx),
            Math.min(1, d.bbox[3] + dy),
          ];
          return { ...d, bbox: nb, confidence: Math.min(0.99, Math.max(0.6, d.confidence + rand(-0.03, 0.03))) };
        });
      }
      setFrame({
        frame_index: idx.current,
        fps: Math.round(rand(11, 18)),
        latency_ms: Math.round(rand(42, 96)),
        detections: persons.current,
        simulated: true,
      });
    }, 700);
    return () => window.clearInterval(tick);
  }, [running]);

  return frame;
}
