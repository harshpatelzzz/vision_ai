import { useMemo, useState } from "react";
import { Database, Search, Lock, Link2, FileSearch } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { EmptyState } from "@/components/ui/States";
import { useBlockchain } from "@/hooks/useApiData";
import { getIpfs } from "@/lib/api";
import { fmtTime, shortHash } from "@/lib/utils";

export default function Ipfs() {
  const { data } = useBlockchain();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const cids = useMemo(() => {
    return (data?.chain ?? [])
      .filter((b) => b.ipfs_cid && b.ipfs_cid !== "GENESIS")
      .map((b) => ({ cid: b.ipfs_cid, index: b.index, ts: b.timestamp, type: b.event?.alert_type || b.event?.type }))
      .reverse();
  }, [data]);

  const filtered = cids.filter((c) => c.cid.toLowerCase().includes(query.toLowerCase()));

  async function inspect(cid: string) {
    setSelected(cid);
    setMeta(null);
    setErr(null);
    try {
      const r = await getIpfs(cid);
      setMeta(r);
    } catch (e: any) {
      setErr(e?.response?.data?.detail ?? "CID not found");
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
      <GlassCard>
        <div className="flex items-center justify-between">
          <SectionTitle>IPFS Metadata Objects</SectionTitle>
          <span className="chip border border-signal-green/30 bg-signal-green/10 text-signal-green"><Lock className="h-3 w-3" /> Fernet Encrypted</span>
        </div>
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-white/10 bg-black/40 px-3">
          <Search className="h-4 w-4 text-white/40" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search CID…" className="flex-1 bg-transparent py-2 font-mono text-sm text-white outline-none placeholder:text-white/25" />
        </div>
        <div className="max-h-[460px] space-y-2 overflow-y-auto pr-1">
          {filtered.length === 0 && <EmptyState label="No CIDs" />}
          {filtered.map((c) => (
            <button key={`${c.index}-${c.cid}`} onClick={() => inspect(c.cid)} className={`flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left transition ${selected === c.cid ? "border-cyan-glow/50 bg-cyan-glow/5" : "border-white/8 bg-white/[0.02] hover:border-white/20"}`}>
              <div className="flex items-center gap-3">
                <Database className="h-4 w-4 text-cyber-400" />
                <div>
                  <p className="font-mono text-xs text-white">{c.cid}</p>
                  <p className="font-mono text-[10px] text-white/40">blk#{c.index} · {c.type} · {fmtTime(c.ts)}</p>
                </div>
              </div>
              <Link2 className="h-3.5 w-3.5 text-white/30" />
            </button>
          ))}
        </div>
      </GlassCard>

      <GlassCard>
        <SectionTitle><span className="flex items-center gap-2"><FileSearch className="h-3.5 w-3.5" /> Object Inspector</span></SectionTitle>
        {!selected && <p className="py-10 text-center font-mono text-[11px] text-white/30">Select a CID to fetch its encrypted payload</p>}
        {selected && (
          <div className="space-y-3">
            <Field label="CID" value={selected} />
            <Field label="Encryption" value="Fernet (AES-128-CBC + HMAC)" accent="text-signal-green" />
            <Field label="Storage" value={meta ? "Retrieved" : err ? "Error" : "Fetching…"} accent={err ? "text-signal-red" : "text-cyber-400"} />
            {err && <p className="rounded-lg border border-signal-red/30 bg-signal-red/5 p-2 font-mono text-[11px] text-signal-red">{err}</p>}
            {meta && (
              <div>
                <p className="hud-label mb-1">Encrypted Payload</p>
                <pre className="max-h-72 overflow-auto rounded-lg bg-black/50 p-3 font-mono text-[10px] leading-relaxed text-cyan-glow/80">
                  {JSON.stringify(meta, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </GlassCard>
    </div>
  );
}

function Field({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-lg border border-white/6 bg-white/[0.02] px-3 py-2">
      <p className="hud-label">{label}</p>
      <p className={`mt-0.5 break-all font-mono text-[11px] ${accent ?? "text-white/80"}`}>{value}</p>
    </div>
  );
}
