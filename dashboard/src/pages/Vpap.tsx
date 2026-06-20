import { useState } from "react";
import { ShieldCheck, ShieldX, FileCheck2, RefreshCw, Lock, Trash2, Network } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { useAttestation } from "@/hooks/useApiData";
import { verifyVpap } from "@/lib/api";
import { useSystem } from "@/store/SystemContext";
import { cn, shortHash } from "@/lib/utils";
import type { VerifyResult } from "@/lib/types";

export default function Vpap() {
  const attest = useAttestation();
  const { pushNotification } = useSystem();
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function onVerify() {
    setBusy(true);
    try {
      const r = await verifyVpap();
      setResult(r);
      pushNotification({
        title: r.status === "valid" ? "VPAP Chain Valid" : "VPAP Tampered",
        message: r.status === "valid" ? `${r.checked_entries} entries verified.` : `Corrupt line ${r.corrupt_line_index}.`,
        severity: r.status === "valid" ? "success" : "critical",
      });
    } finally {
      setBusy(false);
    }
  }

  const models = attest.data?.models ?? {};
  const scripts = attest.data?.scripts ?? {};

  return (
    <div className="space-y-4">
      <GlassCard>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-sky-500/15 ring-1 ring-sky-400/30">
              <Network className="h-5 w-5 text-sky-300" />
            </div>
            <div>
              <p className="font-display text-lg font-bold text-white">VPAP · Verifiable Privacy Attestation</p>
              <p className="font-mono text-[11px] text-white/45">SHA-256 hash-chained JSONL · memory-only frames · model/script attestation</p>
            </div>
          </div>
          <button onClick={onVerify} disabled={busy} className="flex items-center gap-2 rounded-lg border border-cyan-glow/40 bg-cyan-glow/10 px-3 py-2 font-mono text-xs uppercase tracking-wider text-cyan-glow hover:bg-cyan-glow/20 disabled:opacity-50">
            {busy ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <FileCheck2 className="h-3.5 w-3.5" />} Verify VPAP Chain
          </button>
        </div>

        {result && (
          <div className={cn("mt-4 flex items-center gap-3 rounded-xl border p-3", result.status === "valid" ? "border-signal-green/40 bg-signal-green/5" : "border-signal-red/40 bg-signal-red/5")}>
            {result.status === "valid" ? <ShieldCheck className="h-6 w-6 text-signal-green" /> : <ShieldX className="h-6 w-6 text-signal-red" />}
            <div>
              <p className={cn("font-display text-sm font-bold", result.status === "valid" ? "text-signal-green" : "text-signal-red")}>
                {result.status === "valid" ? "PRIVACY CHAIN VERIFIED" : "PRIVACY CHAIN TAMPERED"}
              </p>
              <p className="font-mono text-[11px] text-white/50">{result.checked_entries} entries{result.corrupt_line_index != null ? ` · corrupt @ ${result.corrupt_line_index}` : ""}</p>
            </div>
          </div>
        )}
      </GlassCard>

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: Lock, t: "Memory-Only", d: "Frames held in volatile RAM; never persisted to disk." },
          { icon: Trash2, t: "Frame Deletion", d: "Buffers overwritten each cycle; zeroized on tamper." },
          { icon: ShieldCheck, t: "Verification", d: "Each record chains SHA256(prev + canonical(event))." },
        ].map((c) => (
          <GlassCard key={c.t} className="flex items-start gap-3">
            <c.icon className="h-5 w-5 shrink-0 text-cyan-glow" />
            <div>
              <p className="font-display text-sm font-semibold text-white">{c.t}</p>
              <p className="mt-1 text-xs text-white/55">{c.d}</p>
            </div>
          </GlassCard>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <GlassCard>
          <SectionTitle>Model Attestation</SectionTitle>
          <AttestList items={models} empty="No model hashes" />
        </GlassCard>
        <GlassCard>
          <SectionTitle>Script Attestation</SectionTitle>
          <AttestList items={scripts} empty="No script hashes" />
        </GlassCard>
      </div>
    </div>
  );
}

function AttestList({ items, empty }: { items: Record<string, string>; empty: string }) {
  const entries = Object.entries(items);
  if (entries.length === 0) return <p className="py-6 text-center font-mono text-[11px] text-white/30">{empty}</p>;
  return (
    <div className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
      {entries.map(([path, hash]) => (
        <div key={path} className="flex items-center justify-between rounded-lg border border-white/8 bg-white/[0.02] px-3 py-2">
          <span className="truncate font-mono text-[11px] text-white/70">{path}</span>
          <span className="shrink-0 font-mono text-[10px] text-signal-green">{shortHash(hash, 8, 6)}</span>
        </div>
      ))}
    </div>
  );
}
