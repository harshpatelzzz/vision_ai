import {
  Users, HardHat, ShieldCheck, ShieldX, Shirt, Ban, Crosshair, UserCheck, UserX,
  ShieldAlert, Cpu, Boxes, Database, Lock, Bell,
} from "lucide-react";
import { StatCard } from "@/components/ui/StatCard";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { StatusPill } from "@/components/ui/StatusPill";
import { EventTimeline } from "@/components/widgets/EventTimeline";
import { EdgeNodeMap } from "@/components/widgets/EdgeNodeMap";
import { useChainMetrics } from "@/hooks/useChainMetrics";
import {
  useSecurityStatus, useHardwareSensors, useHardwareStatus, useRfidStatus, useHealth,
} from "@/hooks/useApiData";
import { useSystem } from "@/store/SystemContext";

function HealthBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between font-mono text-[10px] text-white/50">
        <span>{label}</span>
        <span>{value}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${value}%`, background: color }} />
      </div>
    </div>
  );
}

export default function Dashboard() {
  const m = useChainMetrics();
  const security = useSecurityStatus();
  const sensors = useHardwareSensors();
  const hwStatus = useHardwareStatus();
  const rfid = useRfidStatus();
  const health = useHealth();
  const { notifications } = useSystem();

  const hwOnline = sensors.data?.connected || sensors.data?.last?._connected;
  const esp32Online = hwStatus.data?.telemetry_registered || hwOnline;
  const tamper = security.data?.tamper_detected || sensors.data?.last?.tamper;
  const chainValid = m.error ? false : true;

  const compliance = m.helmetOn + m.helmetOff > 0
    ? Math.round((m.helmetOn / (m.helmetOn + m.helmetOff)) * 100)
    : 100;

  return (
    <div className="space-y-5">
      {/* Hero strip */}
      <GlassCard reticle className="overflow-hidden">
        <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill severity={health.isSuccess ? "success" : "critical"} label={health.isSuccess ? "C2 ONLINE" : "C2 OFFLINE"} />
              <StatusPill severity={chainValid ? "success" : "critical"} label={chainValid ? "LEDGER VALID" : "LEDGER TAMPERED"} />
              <StatusPill severity="success" label="PRIVACYGUARD ON" />
              <StatusPill severity={tamper ? "critical" : "success"} label={tamper ? "TAMPER" : "SECURE"} />
            </div>
            <h2 className="mt-4 font-display text-2xl font-bold tracking-wide text-white glow-text">
              Workplace Safety · Edge AI Surveillance
            </h2>
            <p className="mt-1 max-w-xl text-sm text-white/50">
              Privacy-preserving on-device inference with blockchain tamper-evident logging.
              No raw video persisted — only signed metadata committed to the ledger.
            </p>
            <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <p className="hud-label">Ledger Height</p>
                <p className="stat-value text-cyan-glow glow-text">{m.height}</p>
              </div>
              <div>
                <p className="hud-label">Tracked Persons</p>
                <p className="stat-value">{m.persons}</p>
              </div>
              <div>
                <p className="hud-label">Today's Alerts</p>
                <p className="stat-value text-signal-amber">{m.todaysAlerts}</p>
              </div>
              <div>
                <p className="hud-label">Active Alerts</p>
                <p className="stat-value text-signal-red">{notifications.filter((n) => !n.read).length}</p>
              </div>
            </div>
          </div>

          <div className="relative min-h-[220px] rounded-xl border border-white/8 bg-black/20">
            <EdgeNodeMap />
          </div>
        </div>
      </GlassCard>

      {/* Primary stat grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Total Persons" value={m.persons} icon={Users} severity="info" loading={m.loading} />
        <StatCard label="Helmet ✓" value={m.helmetOn} icon={HardHat} severity="success" loading={m.loading} />
        <StatCard label="No Helmet" value={m.helmetOff} icon={ShieldX} severity="warning" loading={m.loading} />
        <StatCard label="Vest ✓" value={m.vestOn} icon={Shirt} severity="success" loading={m.loading} />
        <StatCard label="No Vest" value={m.vestOff} icon={Ban} severity="warning" loading={m.loading} />
        <StatCard label="Intrusions" value={m.intrusions} icon={Crosshair} severity="warning" loading={m.loading} />
        <StatCard label="Authorized" value={m.authorized} icon={UserCheck} severity="success" loading={m.loading} />
        <StatCard label="Unauthorized" value={m.unauthorized} icon={UserX} severity="critical" loading={m.loading} />
        <StatCard label="Unknown RFID" value={m.unknownRfid} icon={ShieldAlert} severity="warning" loading={m.loading} />
        <StatCard label="Tamper Alerts" value={m.tamperAlerts} icon={ShieldAlert} severity="critical" loading={m.loading} />
      </div>

      {/* Subsystem status grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Hardware" value={hwOnline ? "SECURE" : "OFFLINE"} icon={ShieldCheck} severity={hwOnline ? "success" : "critical"} hint={security.data?.mode ?? "monitor"} />
        <StatCard label="ESP32" value={esp32Online ? "LINKED" : "DOWN"} icon={Cpu} severity={esp32Online ? "success" : "warning"} hint={sensors.data?.last?.wifi ? "wifi up" : "serial"} />
        <StatCard label="Blockchain" value={chainValid ? "VALID" : "TAMPER"} icon={Boxes} severity={chainValid ? "success" : "critical"} hint={`h=${m.height}`} />
        <StatCard label="IPFS" value="ENCRYPTED" icon={Database} severity="success" hint="metadata only" />
        <StatCard label="Privacy" value="MEM-ONLY" icon={Lock} severity="success" hint="frames volatile" />
      </div>

      {/* Lower row */}
      <div className="grid gap-4 lg:grid-cols-3">
        <GlassCard className="lg:col-span-2">
          <SectionTitle>System Health</SectionTitle>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-3">
              <HealthBar label="Helmet Compliance" value={compliance} color="#22e3a0" />
              <HealthBar label="Vest Compliance" value={m.vestOn + m.vestOff > 0 ? Math.round((m.vestOn / (m.vestOn + m.vestOff)) * 100) : 100} color="#38bdf8" />
              <HealthBar label="Ledger Integrity" value={chainValid ? 100 : 0} color={chainValid ? "#22e3a0" : "#ff4d61"} />
              <HealthBar label="Edge Uptime" value={health.isSuccess ? 99 : 0} color="#a78bfa" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <MiniStat label="Reader" value={rfid.data?.reader?.running ? "ON" : "OFF"} ok={!!rfid.data?.reader?.running} />
              <MiniStat label="Users" value={String(rfid.data?.access_control?.users_registered ?? "—")} ok />
              <MiniStat label="Granted" value={String(rfid.data?.access_control?.granted ?? 0)} ok />
              <MiniStat label="Denied" value={String(rfid.data?.access_control?.denied ?? 0)} ok={false} />
              <MiniStat label="Temp °C" value={String(sensors.data?.last?.temperature ?? "—")} ok={!sensors.data?.last?.tamper} />
              <MiniStat label="Sensors" value={hwOnline ? "LIVE" : "—"} ok={!!hwOnline} />
            </div>
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle>
            <span className="flex items-center gap-2"><Bell className="h-3.5 w-3.5" /> Event Timeline</span>
          </SectionTitle>
          <EventTimeline limit={30} dense />
        </GlassCard>
      </div>
    </div>
  );
}

function MiniStat({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02] p-3">
      <p className="hud-label">{label}</p>
      <p className={`mt-1 font-display text-lg font-bold ${ok ? "text-signal-green" : "text-signal-amber"}`}>{value}</p>
    </div>
  );
}
