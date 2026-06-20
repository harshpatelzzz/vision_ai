# PoseVision · Edge AI Command Center

Mission-control dashboard for the **Privacy-Preserving Edge AI Workplace Safety
Monitoring** system with blockchain tamper-evident logging. Built to feel like a
defence / ISRO-style command & control console — glassmorphism, cyber-blue glow,
animated telemetry, real-time WebSocket feeds.

## Stack

React 18 · TypeScript · Vite · TailwindCSS · Framer Motion · React Query ·
React Router · Axios · Recharts · React Flow · Lucide · native WebSocket
(+ socket.io-client available). Dark theme only.

## Quick start

```bash
# 1) Start the FastAPI edge node (from the repo root, in secure logging mode)
python -m api.server          # serves http://127.0.0.1:8000

# 2) Start the dashboard
cd dashboard
npm install
npm run dev                   # http://localhost:5173
```

The Vite dev server proxies `/api` and `/ws` to the backend (see
`vite.config.ts`), so **no CORS setup is needed in development**. Point it at a
different backend with `VITE_API_TARGET`:

```bash
VITE_API_TARGET=http://192.168.1.20:8000 npm run dev
```

### Production build

```bash
npm run build      # tsc --noEmit && vite build  → dist/
npm run preview
```

For a deployed build calling the backend directly, set `.env`:

```
VITE_API_BASE=https://edge-node.local:8000
VITE_WS_BASE=wss://edge-node.local:8000
```

and allow the origin on the backend:
`POSEVISION_CORS_ORIGINS=https://dashboard.local python -m api.server`.

## Pages

| Route | Page | Data source |
|-------|------|-------------|
| `/` | Mission Overview | aggregates `/blockchain`, `/security/status`, `/hardware/*`, `/rfid/status` |
| `/live` | Live Monitoring | webcam (getUserMedia) / ESP32-CAM MJPEG + AI overlay |
| `/esp32` | ESP32 Camera | `/hardware/stream`, `/hardware/status`, WS telemetry |
| `/video` | Video Analysis | in-browser file analysis |
| `/hardware` | Hardware Security | `/hardware/sensors` + `/ws/telemetry` gauges |
| `/rfid` | RFID Access | `/rfid/*` (status, users, access-log, last-scan, register, remove) |
| `/blockchain` | Blockchain | `/blockchain`, `/blockchain/verify`, `/tamper/simulate` |
| `/merkle` | Merkle Tree | live Web-Crypto SHA-256 tree over block hashes + `/merkle/root` |
| `/privacy` | Privacy Layer | PrivacyGuard pipeline visualization |
| `/vpap` | VPAP | `/verify`, `/attestation` |
| `/ipfs` | IPFS | block `ipfs_cid` list + `/ipfs/{cid}` |
| `/analytics` | Analytics | Recharts over the ledger |
| `/reports` | Reports | CSV / JSON / Print-PDF export with date filters |
| `/settings` | Settings | local mirror of `config.yaml` |

## Architecture

```
src/
  lib/        api.ts (all endpoints) · types.ts · nav.ts · utils.ts
  hooks/      useApiData (React Query) · useWebSocket · useChainMetrics ·
              useLiveDetections · useClock
  store/      SystemContext (notifications + live log console + threat level)
  components/
    ui/       GlassCard · StatCard · StatusPill · Gauge · States
    layout/   AppShell · Sidebar · TopHeader · NotificationPanel ·
              LiveLogConsole · TelemetryBridge
    widgets/  CameraStage · DetectionPanel · EventTimeline · EdgeNodeMap
  pages/      one file per route
```

## Live detection feed

The live AI overlay (`useLiveDetections`) currently renders a **clearly-labelled
simulated** detection stream, because the backend's `/ws/live-events` channel is
a reserved placeholder (see `api/server.py`). The `Detection` type already
matches the normalized event schema (ppe, posture, intrusion, access), so when
the edge pipeline starts publishing per-frame detections on that channel, swap
the simulator for `useWebSocket("/ws/live-events")` — no UI changes needed.

All other panels (dashboard stats, timeline, blockchain, merkle, hardware, RFID,
analytics, reports, IPFS, VPAP) consume **real** backend data.

## Backend note

The only backend change required for the browser is permissive **CORS**
(added to `api/server.py`). Everything else consumes existing endpoints.
