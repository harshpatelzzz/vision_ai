import { useState } from "react";
import { Thermometer, Ruler, Sun, Compass, ToggleLeft, Wifi, BatteryCharging, Cpu, RotateCcw } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { Gauge } from "@/components/ui/Gauge";
import { StatusPill } from "@/components/ui/StatusPill";
import { WarningBanner } from "@/components/ui/States";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useHardwareSensors, useHardwareStatus, useSecurityStatus } from "@/hooks/useApiData";
import { resetHardware, WS_PATHS } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import type { SensorSnapshot, Severity } from "@/lib/types";

function tempSeverity(t?: number): Severity {
  if (t == null) return "info";
  if (t >= 55) return "critical";
  if (t >= 45) return "warning";
  return "success";
}
function distSeverity(d?: number): Severity {
  if (d == null) return "info";
  if (d < 50) return "critical";
  if (d < 120) return "warning";
  return "success";
}

export default function HardwareSecurity() {
  const sensors = useHardwareSensors();
  const status = useHardwareStatus();
  const security = useSecurityStatus();
  const qc = useQueryClient();
  const [live, setLive] = useState<SensorSnapshot | null>(null);

  useWebSocket<{ telemetry: SensorSnapshot }>({
    path: WS_PATHS.telemetry,
    onMessage: (d) => d?.telemetry && Object.keys(d.telemetry).length > 0 && setLive(d.telemetry),
  });

  const s: SensorSnapshot = { ...(sensors.data?.last ?? {}), ...(live ?? {}) };
  const connected = Boolean(s._connected ?? sensors.data?.connected);
  const tamper = Boolean(s.tamper || security.data?.tamper_detected);

  async function onReset() {
    await resetHardware();
    qc.invalidateQueries({ queryKey: ["hw-sensors"] });
  }

  const cards = [
    { label: "ESP32", value: connected ? "CONNECTED" : "OFFLINE", icon: Cpu, sev: (connected ? "success" : "critical") as Severity },
    { label: "Limit Switch", value: s.limit_switch_closed === false ? "OPEN" : "CLOSED", icon: ToggleLeft, sev: (s.limit_switch_closed === false ? "critical" : "success") as Severity },
    { label: "WiFi Link", value: s.wifi ? "UP" : "DOWN", icon: Wifi, sev: (s.wifi ? "success" : "warning") as Severity },
    { label: "Battery", value: "N/A", icon: BatteryCharging, sev: "info" as Severity },
  ];

  return (
    <div className="space-y-4">
      {tamper && <WarningBanner>Tamper signal active — enclosure integrity compromised. Pipeline halt + zeroization may have triggered.</WarningBanner>}

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <GlassCard>
          <div className="flex items-center justify-between">
            <SectionTitle>Sensor Telemetry</SectionTitle>
            <div className="flex items-center gap-2">
              <StatusPill severity={connected ? "success" : "critical"} label={connected ? "LIVE" : "NO LINK"} />
              <button onClick={onReset} className="flex items-center gap-1 rounded-lg border border-white/10 px-2 py-1 font-mono text-[10px] text-white/50 hover:bg-white/5">
                <RotateCcw className="h-3 w-3" /> Reset
              </button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 py-2 sm:grid-cols-4">
            <Gauge label="Temp °C" value={s.temperature} min={0} max={80} unit="°C" severity={tempSeverity(s.temperature)} />
            <Gauge label="Distance" value={s.distance} min={0} max={2000} unit="mm" severity={distSeverity(s.distance)} />
            <Gauge label="Light" value={s.light} min={0} max={4095} unit="adc" severity={s.light && s.light > 3800 ? "warning" : "info"} />
            <Gauge label="Orientation" value={s.orientation} min={0} max={360} unit="deg" severity="info" />
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle>Hardware Status</SectionTitle>
          <div className="grid grid-cols-2 gap-3">
            {cards.map((c) => (
              <div key={c.label} className="glass flex items-center gap-3 !p-3">
                <div className={`grid h-10 w-10 place-items-center rounded-lg bg-white/5 ${
                  c.sev === "success" ? "text-signal-green" : c.sev === "critical" ? "text-signal-red" : c.sev === "warning" ? "text-signal-amber" : "text-cyber-400"
                }`}>
                  <c.icon className="h-5 w-5" />
                </div>
                <div>
                  <p className="hud-label">{c.label}</p>
                  <p className="font-display text-sm font-bold text-white">{c.value}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 space-y-2 rounded-xl border border-white/8 bg-white/[0.02] p-3 font-mono text-[11px] text-white/55">
            <Row k="Monitor mode" v={security.data?.mode ?? "—"} />
            <Row k="Monitor running" v={String(security.data?.monitor_running ?? "—")} />
            <Row k="Telemetry registered" v={String(status.data?.telemetry_registered ?? false)} />
            <Row k="Stream configured" v={String(status.data?.stream_url_configured ?? false)} />
            <Row k="Last error" v={s._last_error ?? "none"} />
            <Row k="Uptime" v={s.uptime_ms ? `${Math.round((s.uptime_ms as number) / 1000)}s` : "—"} />
          </div>
        </GlassCard>
      </div>

      <GlassCard>
        <SectionTitle>Threshold Reference (config.yaml · esp32_telemetry.thresholds)</SectionTitle>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { k: "temp_max_c", v: "55.0", c: "text-signal-red" },
            { k: "distance_min_mm", v: "50", c: "text-signal-amber" },
            { k: "distance_max_mm", v: "8000", c: "text-cyber-400" },
            { k: "orientation_delta", v: "35°", c: "text-signal-violet" },
          ].map((t) => (
            <div key={t.k} className="rounded-xl border border-white/8 bg-black/20 p-3">
              <p className="hud-label">{t.k}</p>
              <p className={`mt-1 font-display text-xl font-bold ${t.c}`}>{t.v}</p>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-white/35">{k}</span>
      <span className="text-white/75">{v}</span>
    </div>
  );
}
