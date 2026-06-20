import { useEffect, useState } from "react";
import { Camera, Gauge, Crosshair, EyeOff, Cpu, Boxes, Save, RotateCcw } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { useSystem } from "@/store/SystemContext";

interface SettingsState {
  cameraSource: string;
  targetFps: number;
  yoloConf: number;
  iouPersonPpe: number;
  tripwireEnabled: boolean;
  privacyMemoryOnly: boolean;
  allowVideoExport: boolean;
  hardwareMode: string;
  blockchainSecure: boolean;
}

const DEFAULTS: SettingsState = {
  cameraSource: "0",
  targetFps: 12,
  yoloConf: 0.25,
  iouPersonPpe: 0.25,
  tripwireEnabled: true,
  privacyMemoryOnly: true,
  allowVideoExport: false,
  hardwareMode: "simulation",
  blockchainSecure: true,
};

const KEY = "posevision.settings";

export default function Settings() {
  const { pushNotification } = useSystem();
  const [s, setS] = useState<SettingsState>(DEFAULTS);

  useEffect(() => {
    const raw = localStorage.getItem(KEY);
    if (raw) try { setS({ ...DEFAULTS, ...JSON.parse(raw) }); } catch { /* ignore */ }
  }, []);

  function set<K extends keyof SettingsState>(k: K, v: SettingsState[K]) {
    setS((prev) => ({ ...prev, [k]: v }));
  }
  function save() {
    localStorage.setItem(KEY, JSON.stringify(s));
    pushNotification({ title: "Settings Saved", message: "Stored locally. Mirror to config.yaml on the edge node to apply.", severity: "success" });
  }
  function reset() {
    setS(DEFAULTS);
    localStorage.removeItem(KEY);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[11px] text-white/40">
          Mirrors <span className="text-cyber-400">config/config.yaml</span>. Saved to browser; the edge node reads YAML at launch.
        </p>
        <div className="flex gap-2">
          <button onClick={reset} className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 font-mono text-xs text-white/60 hover:bg-white/5"><RotateCcw className="h-3.5 w-3.5" /> Reset</button>
          <button onClick={save} className="flex items-center gap-1.5 rounded-lg border border-cyan-glow/40 bg-cyan-glow/10 px-3 py-2 font-mono text-xs uppercase tracking-wider text-cyan-glow"><Save className="h-3.5 w-3.5" /> Save</button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <GlassCard>
          <SectionTitle><span className="flex items-center gap-2"><Camera className="h-3.5 w-3.5" /> Camera</span></SectionTitle>
          <Text label="Source (index / esp32cam)" value={s.cameraSource} onChange={(v) => set("cameraSource", v)} />
          <Range label="Target FPS" value={s.targetFps} min={1} max={30} step={1} onChange={(v) => set("targetFps", v)} />
        </GlassCard>

        <GlassCard>
          <SectionTitle><span className="flex items-center gap-2"><Gauge className="h-3.5 w-3.5" /> Inference</span></SectionTitle>
          <Range label="YOLO Confidence" value={s.yoloConf} min={0.1} max={0.9} step={0.05} onChange={(v) => set("yoloConf", v)} />
          <Range label="IoU Person↔PPE" value={s.iouPersonPpe} min={0.1} max={0.9} step={0.05} onChange={(v) => set("iouPersonPpe", v)} />
        </GlassCard>

        <GlassCard>
          <SectionTitle><span className="flex items-center gap-2"><Crosshair className="h-3.5 w-3.5" /> Tripwire &amp; Privacy</span></SectionTitle>
          <Toggle label="Tripwire enabled" value={s.tripwireEnabled} onChange={(v) => set("tripwireEnabled", v)} />
          <Toggle label="Privacy: memory-only frames" value={s.privacyMemoryOnly} onChange={(v) => set("privacyMemoryOnly", v)} />
          <Toggle label="Allow annotated video export" value={s.allowVideoExport} onChange={(v) => set("allowVideoExport", v)} />
        </GlassCard>

        <GlassCard>
          <SectionTitle><span className="flex items-center gap-2"><Cpu className="h-3.5 w-3.5" /> Hardware &amp; Blockchain</span></SectionTitle>
          <Select label="Hardware monitor mode" value={s.hardwareMode} options={["simulation", "gpio", "serial"]} onChange={(v) => set("hardwareMode", v)} />
          <Toggle label="Secure logging (blockchain)" value={s.blockchainSecure} onChange={(v) => set("blockchainSecure", v)} />
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-white/8 bg-black/20 px-3 py-2 font-mono text-[10px] text-white/45">
            <Boxes className="h-3.5 w-3.5 text-cyber-400" /> PoA validators: node-a · node-b · node-c
          </div>
        </GlassCard>
      </div>
    </div>
  );
}

function Text({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="mb-3">
      <p className="hud-label mb-1">{label}</p>
      <input value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 font-mono text-sm text-white outline-none focus:border-cyan-glow/50" />
    </div>
  );
}
function Range({ label, value, min, max, step, onChange }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void }) {
  return (
    <div className="mb-3">
      <div className="mb-1 flex justify-between"><p className="hud-label">{label}</p><span className="font-mono text-xs text-cyan-glow">{value}</span></div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-cyan-glow" />
    </div>
  );
}
function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!value)} className="mb-2 flex w-full items-center justify-between rounded-lg border border-white/8 bg-white/[0.02] px-3 py-2">
      <span className="text-sm text-white/70">{label}</span>
      <span className={`relative h-5 w-9 rounded-full transition ${value ? "bg-signal-green/70" : "bg-white/15"}`}>
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${value ? "left-[18px]" : "left-0.5"}`} />
      </span>
    </button>
  );
}
function Select({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div className="mb-3">
      <p className="hud-label mb-1">{label}</p>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-cyan-glow/50">
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}
