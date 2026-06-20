import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ScanLine, UserPlus, Trash2, ShieldCheck, ShieldX, HelpCircle, Radio } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { StatusPill } from "@/components/ui/StatusPill";
import { EmptyState } from "@/components/ui/States";
import { useRfidStatus, useRfidUsers, useRfidAccessLog, useRfidLastScan } from "@/hooks/useApiData";
import { registerRfid, removeRfid } from "@/lib/api";
import { useSystem } from "@/store/SystemContext";
import { cn, fmtTime } from "@/lib/utils";
import type { AccessBlock } from "@/lib/types";

const ROLES = ["Admin", "Guard", "Engineer", "Worker", "Visitor"];
const ZONES = ["ZoneA", "ZoneB", "ZoneC"];

export default function RfidAccess() {
  const status = useRfidStatus();
  const users = useRfidUsers();
  const log = useRfidAccessLog(60);
  const lastScan = useRfidLastScan();
  const qc = useQueryClient();
  const { pushNotification } = useSystem();

  const [form, setForm] = useState({ uid: "", name: "", role: "Worker", zones: ["ZoneA"] });
  const [busy, setBusy] = useState(false);

  const reader = status.data?.reader;
  const ac = status.data?.access_control;

  async function onRegister() {
    if (!form.name) return pushNotification({ title: "Validation", message: "Name required.", severity: "warning" });
    setBusy(true);
    try {
      await registerRfid({ uid: form.uid || undefined, name: form.name, role: form.role, allowed_zones: form.zones });
      pushNotification({ title: "RFID Registered", message: `${form.name} (${form.role}) enrolled.`, severity: "success" });
      setForm({ uid: "", name: "", role: "Worker", zones: ["ZoneA"] });
      qc.invalidateQueries({ queryKey: ["rfid-users"] });
    } catch (e: any) {
      pushNotification({ title: "Registration failed", message: e?.response?.data?.detail ?? "Error", severity: "critical" });
    } finally {
      setBusy(false);
    }
  }

  async function onRemove(uid: string) {
    await removeRfid(uid);
    qc.invalidateQueries({ queryKey: ["rfid-users"] });
    pushNotification({ title: "RFID Removed", message: `${uid} revoked.`, severity: "info" });
  }

  function toggleZone(z: string) {
    setForm((f) => ({ ...f, zones: f.zones.includes(z) ? f.zones.filter((x) => x !== z) : [...f.zones, z] }));
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <Kpi label="Reader" value={reader?.running ? "ONLINE" : "OFFLINE"} sev={reader?.running ? "success" : "critical"} sub={reader?.mode} />
        <Kpi label="Registered" value={String(ac?.users_registered ?? "—")} sev="info" sub="tags" />
        <Kpi label="Granted" value={String(ac?.granted ?? 0)} sev="success" sub="access events" />
        <Kpi label="Denied" value={String(ac?.denied ?? 0)} sev="critical" sub="violations" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        {/* Live scans + access log */}
        <GlassCard>
          <div className="flex items-center justify-between">
            <SectionTitle>Live Access Log</SectionTitle>
            <StatusPill severity={reader?.connected ? "success" : "warning"} label={reader?.connected ? "SCANNING" : "IDLE"} />
          </div>

          <div className="mb-3 flex items-center gap-3 rounded-xl border border-cyan-glow/25 bg-cyan-glow/5 p-3">
            <Radio className="h-5 w-5 animate-pulse-glow text-cyan-glow" />
            <div className="min-w-0">
              <p className="hud-label">Last Scan</p>
              <p className="truncate font-mono text-sm text-white">
                {lastScan.data?.last_scan ? `${lastScan.data.last_scan.uid} · ${fmtTime(lastScan.data.last_scan.timestamp)}` : "— awaiting tag —"}
              </p>
            </div>
          </div>

          <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
            {(!log.data?.events || log.data.events.length === 0) && <EmptyState label="No access events" />}
            {[...(log.data?.events ?? [])].reverse().map((e: AccessBlock, i) => <AccessRow key={i} e={e} />)}
          </div>
        </GlassCard>

        {/* Registration + users */}
        <div className="space-y-4">
          <GlassCard>
            <SectionTitle>Enroll Tag</SectionTitle>
            <div className="space-y-2.5">
              <Input label="UID (blank = use last scan)" value={form.uid} onChange={(v) => setForm((f) => ({ ...f, uid: v }))} placeholder="A1:B2:C3:D4" />
              <Input label="Name" value={form.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} placeholder="J. Doe" />
              <div>
                <p className="hud-label mb-1">Role</p>
                <select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))} className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-cyan-glow/50">
                  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <p className="hud-label mb-1.5">Allowed Zones</p>
                <div className="flex gap-2">
                  {ZONES.map((z) => (
                    <button key={z} onClick={() => toggleZone(z)} className={cn("flex-1 rounded-lg border px-2 py-1.5 font-mono text-[11px]", form.zones.includes(z) ? "border-cyan-glow/50 bg-cyan-glow/15 text-cyan-glow" : "border-white/10 text-white/40")}>
                      {z}
                    </button>
                  ))}
                </div>
              </div>
              <button onClick={onRegister} disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-lg border border-signal-green/40 bg-signal-green/10 px-3 py-2.5 font-mono text-xs uppercase tracking-wider text-signal-green hover:bg-signal-green/20 disabled:opacity-50">
                <UserPlus className="h-4 w-4" /> Register Tag
              </button>
            </div>
          </GlassCard>

          <GlassCard>
            <SectionTitle>Authorized Personnel</SectionTitle>
            <div className="max-h-[260px] space-y-2 overflow-y-auto pr-1">
              {users.data && Object.entries(users.data.users).map(([uid, u]) => (
                <div key={uid} className="flex items-center justify-between rounded-lg border border-white/8 bg-white/[0.02] px-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-white">{u.name}</p>
                    <p className="truncate font-mono text-[10px] text-white/40">{uid} · {u.role} · {u.allowed_zones.join(",")}</p>
                  </div>
                  <button onClick={() => onRemove(uid)} className="rounded p-1.5 text-white/30 hover:bg-signal-red/10 hover:text-signal-red"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              ))}
              {(!users.data || Object.keys(users.data.users).length === 0) && <EmptyState label="No registered tags" />}
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}

function AccessRow({ e }: { e: AccessBlock }) {
  const known = e.decision !== "UNKNOWN_TAG";
  const ok = e.authorized;
  return (
    <div className={cn("flex items-center gap-3 rounded-xl border p-2.5", ok ? "border-signal-green/25 bg-signal-green/5" : known ? "border-signal-amber/30 bg-signal-amber/5" : "border-signal-red/40 bg-signal-red/8")}>
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-black/30">
        {ok ? <ShieldCheck className="h-4 w-4 text-signal-green" /> : known ? <ShieldX className="h-4 w-4 text-signal-amber" /> : <HelpCircle className="h-4 w-4 text-signal-red" />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-xs font-semibold text-white">{e.name ?? "Unknown Tag"} <span className="text-white/40">· {e.role ?? "—"}</span></p>
          <span className="shrink-0 font-mono text-[9px] text-white/35">{fmtTime(e.timestamp)}</span>
        </div>
        <p className="truncate font-mono text-[10px] text-white/45">{e.uid ?? "no-uid"} · {e.zone ?? "?"} · {e.event_type}</p>
      </div>
    </div>
  );
}

function Kpi({ label, value, sev, sub }: { label: string; value: string; sev: "success" | "critical" | "info"; sub?: string }) {
  const color = sev === "success" ? "text-signal-green" : sev === "critical" ? "text-signal-red" : "text-cyber-400";
  return (
    <GlassCard className="!p-3">
      <p className="hud-label">{label}</p>
      <p className={cn("stat-value", color)}>{value}</p>
      {sub && <p className="font-mono text-[10px] text-white/35">{sub}</p>}
    </GlassCard>
  );
}

function Input({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <p className="hud-label mb-1">{label}</p>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 font-mono text-sm text-white outline-none placeholder:text-white/25 focus:border-cyan-glow/50" />
    </div>
  );
}
