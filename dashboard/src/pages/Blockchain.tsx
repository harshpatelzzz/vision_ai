import { useMemo, useState } from "react";
import ReactFlow, { Background, BackgroundVariant, Handle, Position, type Node, type Edge } from "reactflow";
import { motion, AnimatePresence } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, ShieldX, Boxes, Fingerprint, GitBranch, Database, X, Zap, RefreshCw } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { LoadingState, ErrorState } from "@/components/ui/States";
import { useBlockchain } from "@/hooks/useApiData";
import { verifyBlockchain, simulateTamper } from "@/lib/api";
import { cn, eventLabel, fmtTime, shortHash } from "@/lib/utils";
import { useSystem } from "@/store/SystemContext";
import type { Block, BlockchainVerifyResult } from "@/lib/types";

function BlockNode({ data }: { data: { block: Block; tampered: boolean; onClick: () => void } }) {
  const { block, tampered, onClick } = data;
  const type = block.event?.alert_type || block.event?.type || "EVENT";
  return (
    <div
      onClick={onClick}
      className={cn(
        "w-[230px] cursor-pointer rounded-xl border bg-navy-900/90 p-3 backdrop-blur transition-all hover:scale-[1.03]",
        tampered ? "border-signal-red/60 shadow-glow-red" : "border-signal-green/40 shadow-glow-green",
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-cyan-glow" />
      <div className="flex items-center justify-between">
        <span className="font-display text-sm font-bold text-white">#{block.index}</span>
        <span className={cn("chip border text-[9px]", tampered ? "border-signal-red/40 text-signal-red" : "border-signal-green/40 text-signal-green")}>
          {tampered ? <ShieldX className="h-3 w-3" /> : <ShieldCheck className="h-3 w-3" />}
          {tampered ? "TAMPER" : "VALID"}
        </span>
      </div>
      <p className="mt-1 truncate text-[11px] font-medium text-cyan-glow">{eventLabel(type)}</p>
      <div className="mt-2 space-y-0.5 font-mono text-[9px] text-white/45">
        <p className="truncate">hash {shortHash(block.hash, 8, 6)}</p>
        <p className="truncate">merkle {shortHash(block.merkle_root, 8, 4)}</p>
        <p className="truncate">cid {block.ipfs_cid}</p>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-cyan-glow" />
    </div>
  );
}

const nodeTypes = { block: BlockNode };

export default function BlockchainPage() {
  const { data, isLoading, isError } = useBlockchain();
  const qc = useQueryClient();
  const { pushNotification, pushLog } = useSystem();
  const [selected, setSelected] = useState<Block | null>(null);
  const [verify, setVerify] = useState<BlockchainVerifyResult | null>(null);
  const [busy, setBusy] = useState(false);

  const corruptIdx = data?.validation?.status === "tampered" ? data.validation.corrupt_index : verify?.corrupt_block_index ?? null;

  const { nodes, edges } = useMemo(() => {
    const chain = data?.chain ?? [];
    const view = chain.slice(-14);
    const nodes: Node[] = view.map((b, i) => ({
      id: String(b.index),
      type: "block",
      position: { x: 60 + (i % 2) * 30, y: i * 150 },
      data: { block: b, tampered: corruptIdx != null && b.index >= corruptIdx, onClick: () => setSelected(b) },
    }));
    const edges: Edge[] = view.slice(1).map((b, i) => ({
      id: `e-${view[i].index}-${b.index}`,
      source: String(view[i].index),
      target: String(b.index),
      animated: true,
      style: { stroke: corruptIdx != null && b.index >= corruptIdx ? "#ff4d61" : "#22e3a0", strokeWidth: 2 },
    }));
    return { nodes, edges };
  }, [data, corruptIdx]);

  async function onVerify() {
    setBusy(true);
    try {
      const r = await verifyBlockchain();
      setVerify(r);
      pushLog({ source: "BLOCKCHAIN", level: r.status === "valid" ? "success" : "critical", message: `verify → ${r.status} ${r.reason}` });
      pushNotification({
        title: r.status === "valid" ? "Blockchain Verified" : "Blockchain Failure",
        message: r.status === "valid" ? "All blocks signed & chained correctly." : `Corrupt block ${r.corrupt_block_index}: ${r.reason}`,
        severity: r.status === "valid" ? "success" : "critical",
      });
    } finally {
      setBusy(false);
    }
  }

  async function onTamper() {
    setBusy(true);
    try {
      const r = await simulateTamper();
      setVerify(r);
      await qc.invalidateQueries({ queryKey: ["blockchain"] });
      pushNotification({ title: "Tamper Simulated", message: `Block ${r.corrupt_block_index} altered — chain now ${r.status}.`, severity: "warning" });
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) return <LoadingState label="Loading ledger" />;
  if (isError) return <ErrorState title="Ledger unreachable" message="Start the API in secure logging mode to expose the blockchain." />;

  const valid = data?.validation?.status !== "tampered" && verify?.status !== "tampered";

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
      <div className="space-y-4">
        <GlassCard>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-xl bg-cyber-500/15 ring-1 ring-cyan-glow/30">
                <Boxes className="h-5 w-5 text-cyan-glow" />
              </div>
              <div>
                <p className="font-display text-lg font-bold text-white">Tamper-Evident Ledger</p>
                <p className="font-mono text-[11px] text-white/45">PoA · RSA-signed · Merkle-rooted · IPFS-anchored</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={onVerify} disabled={busy} className="flex items-center gap-2 rounded-lg border border-cyan-glow/40 bg-cyan-glow/10 px-3 py-2 font-mono text-xs uppercase tracking-wider text-cyan-glow hover:bg-cyan-glow/20 disabled:opacity-50">
                {busy ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />} Verify Chain
              </button>
              <button onClick={onTamper} disabled={busy} className="flex items-center gap-2 rounded-lg border border-signal-red/40 bg-signal-red/10 px-3 py-2 font-mono text-xs uppercase tracking-wider text-signal-red hover:bg-signal-red/20 disabled:opacity-50">
                <Zap className="h-3.5 w-3.5" /> Simulate Tamper
              </button>
            </div>
          </div>

          <AnimatePresence>
            {(verify || data?.validation) && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className={cn(
                  "mt-4 flex items-center gap-3 rounded-xl border p-3",
                  valid ? "border-signal-green/40 bg-signal-green/5" : "border-signal-red/40 bg-signal-red/5",
                )}
              >
                {valid ? <ShieldCheck className="h-6 w-6 text-signal-green" /> : <ShieldX className="h-6 w-6 text-signal-red" />}
                <div>
                  <p className={cn("font-display text-sm font-bold", valid ? "text-signal-green" : "text-signal-red")}>
                    {valid ? "CHAIN INTEGRITY VERIFIED" : "CHAIN TAMPERED"}
                  </p>
                  <p className="font-mono text-[11px] text-white/50">
                    {valid ? `${data?.height ?? 0} blocks · all signatures valid` : `Corrupt at block ${corruptIdx} · ${verify?.reason ?? data?.validation?.reason}`}
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat icon={Boxes} label="Height" value={String(data?.height ?? 0)} />
            <Stat icon={Fingerprint} label="Latest Hash" value={shortHash(data?.latest_hash, 6, 4)} />
            <Stat icon={GitBranch} label="Merkle Root" value={shortHash(data?.latest_merkle_root, 6, 4)} />
            <Stat icon={Database} label="Status" value={valid ? "VALID" : "TAMPER"} accent={valid ? "text-signal-green" : "text-signal-red"} />
          </div>
        </GlassCard>

        <GlassCard className="!p-0">
          <div className="px-4 pt-4"><SectionTitle>Chain Visualization</SectionTitle></div>
          <div className="h-[520px] w-full">
            <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }} nodesDraggable={false} nodesConnectable={false} elementsSelectable>
              <Background variant={BackgroundVariant.Dots} gap={28} size={1} color="#1e90ff33" />
            </ReactFlow>
          </div>
        </GlassCard>
      </div>

      {/* Inspector */}
      <GlassCard className="flex h-fit flex-col">
        <SectionTitle>Block Inspector</SectionTitle>
        {!selected && <p className="py-8 text-center font-mono text-[11px] text-white/30">Select a block to inspect</p>}
        {selected && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-display text-lg font-bold text-cyan-glow">Block #{selected.index}</span>
              <button onClick={() => setSelected(null)} className="rounded p-1 text-white/40 hover:bg-white/5"><X className="h-4 w-4" /></button>
            </div>
            <Field label="Timestamp" value={fmtTime(selected.timestamp)} />
            <Field label="Event" value={eventLabel(selected.event?.alert_type || selected.event?.type)} />
            <Field label="Person" value={String(selected.event?.person_id ?? "—")} />
            <Field label="Zone" value={selected.event?.access?.zone ?? "—"} />
            <Field label="Hash" value={selected.hash} mono />
            <Field label="Prev Hash" value={selected.previous_hash} mono />
            <Field label="Merkle Root" value={selected.merkle_root} mono />
            <Field label="Signature" value={shortHash(selected.signature, 16, 8)} mono />
            <Field label="IPFS CID" value={selected.ipfs_cid} mono />
            <div>
              <p className="hud-label mb-1">Raw JSON</p>
              <pre className="max-h-56 overflow-auto rounded-lg bg-black/50 p-3 font-mono text-[10px] leading-relaxed text-cyan-glow/80">
                {JSON.stringify(selected.event, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </GlassCard>
    </div>
  );
}

function Stat({ icon: Icon, label, value, accent }: { icon: typeof Boxes; label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02] p-3">
      <div className="flex items-center gap-1.5 text-white/40"><Icon className="h-3.5 w-3.5" /><span className="hud-label">{label}</span></div>
      <p className={cn("mt-1 truncate font-mono text-sm font-bold", accent ?? "text-white")}>{value}</p>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-lg border border-white/6 bg-white/[0.02] px-3 py-2">
      <p className="hud-label">{label}</p>
      <p className={cn("mt-0.5 break-all text-xs text-white/80", mono && "font-mono text-[10px]")}>{value}</p>
    </div>
  );
}
