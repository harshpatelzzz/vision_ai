import { Menu, Bell, Activity, Lock, ShieldCheck, Boxes, Radio } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useClock, useMissionTimer } from "@/hooks/useClock";
import { useHealth, useSecurityStatus, useBlockchain, useHardwareSensors } from "@/hooks/useApiData";
import { NAV } from "@/lib/nav";
import { deriveThreatLevel, useSystem } from "@/store/SystemContext";
import { cn } from "@/lib/utils";

function pageTitle(path: string): string {
  if (path === "/") return "Mission Overview";
  const item = NAV.find((n) => n.path === path);
  return item?.label ?? "Console";
}

function SecChip({ ok, label, icon: Icon }: { ok: boolean; label: string; icon: typeof Lock }) {
  return (
    <div
      className={cn(
        "hidden items-center gap-1.5 rounded-lg border px-2.5 py-1.5 xl:flex",
        ok
          ? "border-signal-green/30 bg-signal-green/5 text-signal-green"
          : "border-signal-red/30 bg-signal-red/5 text-signal-red",
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      <span className="font-mono text-[10px] uppercase tracking-wider">{label}</span>
    </div>
  );
}

export function TopHeader({
  onMenu,
  onToggleNotifications,
}: {
  onMenu: () => void;
  onToggleNotifications: () => void;
}) {
  const now = useClock();
  const mission = useMissionTimer();
  const location = useLocation();
  const { notifications } = useSystem();
  const unread = notifications.filter((n) => !n.read).length;

  const health = useHealth();
  const security = useSecurityStatus();
  const chain = useBlockchain();
  const sensors = useHardwareSensors();

  const apiOnline = health.isSuccess;
  const chainValid = chain.data?.validation?.status !== "tampered";
  const privacyOn = true; // PrivacyGuard is always-on in the edge pipeline
  const hwSecure = !(security.data?.tamper_detected || sensors.data?.last?.tamper);

  const threat = deriveThreatLevel({
    tamper: security.data?.tamper_detected,
    chainTampered: !chainValid,
    sensorTamper: Boolean(sensors.data?.last?.tamper),
  });

  const threatColor =
    threat.level === "CRITICAL"
      ? "text-signal-red border-signal-red/40 bg-signal-red/10"
      : threat.level === "ELEVATED"
        ? "text-signal-amber border-signal-amber/40 bg-signal-amber/10"
        : "text-signal-green border-signal-green/40 bg-signal-green/10";

  return (
    <header className="panel z-20 flex items-center gap-3 rounded-bl-2xl px-4 py-3">
      <button onClick={onMenu} className="rounded-lg p-2 text-white/60 hover:bg-white/5 lg:hidden">
        <Menu className="h-5 w-5" />
      </button>

      <div className="min-w-0">
        <h1 className="truncate font-display text-base font-semibold tracking-wide text-white sm:text-lg">
          {pageTitle(location.pathname)}
        </h1>
        <div className="flex items-center gap-2 font-mono text-[10px] text-white/40">
          <span className={cn("h-1.5 w-1.5 rounded-full", apiOnline ? "bg-signal-green animate-pulse-glow" : "bg-signal-red")} />
          {apiOnline ? "EDGE NODE ONLINE" : "EDGE NODE OFFLINE"}
          <span className="text-white/20">·</span>
          <Radio className="h-3 w-3" /> T+{mission}
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2">
        {/* security indicators */}
        <SecChip ok={chainValid} label="Chain" icon={Boxes} />
        <SecChip ok={privacyOn} label="Privacy" icon={Lock} />
        <SecChip ok={hwSecure} label="Hardware" icon={ShieldCheck} />

        {/* threat level */}
        <div className={cn("flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5", threatColor)}>
          <Activity className="h-3.5 w-3.5" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider">
            {threat.level}
          </span>
        </div>

        {/* clock */}
        <div className="hidden text-right md:block">
          <p className="font-display text-sm font-bold tabular-nums text-white">
            {now.toLocaleTimeString("en-GB", { hour12: false })}
          </p>
          <p className="font-mono text-[9px] uppercase tracking-wider text-white/40">
            {now.toLocaleDateString("en-GB")} · {Intl.DateTimeFormat().resolvedOptions().timeZone}
          </p>
        </div>

        <button
          onClick={onToggleNotifications}
          className="relative rounded-lg border border-white/10 p-2 text-white/60 hover:bg-white/5"
        >
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-signal-red px-1 font-mono text-[9px] font-bold text-white shadow-glow-red">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}
