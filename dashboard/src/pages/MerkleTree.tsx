import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { GitBranch, RefreshCw } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { useBlockchain, useMerkleRoot } from "@/hooks/useApiData";
import { shortHash } from "@/lib/utils";

async function sha256Hex(input: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

interface MNode {
  hash: string;
  children?: MNode[];
}

async function buildMerkle(leaves: string[]): Promise<MNode | null> {
  if (leaves.length === 0) return null;
  let level: MNode[] = leaves.map((h) => ({ hash: h }));
  while (level.length > 1) {
    const next: MNode[] = [];
    for (let i = 0; i < level.length; i += 2) {
      const a = level[i];
      const b = level[i + 1] ?? level[i];
      const parent = await sha256Hex(a.hash + b.hash);
      next.push({ hash: parent, children: a === b ? [a] : [a, b] });
    }
    level = next;
  }
  return level[0];
}

function TreeNode({ node, depth, root }: { node: MNode; depth: number; root?: boolean }) {
  const color = root ? "#22e3a0" : depth === 0 ? "#38bdf8" : "#a78bfa";
  return (
    <div className="flex flex-col items-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        className="rounded-lg border bg-navy-900/80 px-3 py-1.5 font-mono text-[10px]"
        style={{ borderColor: `${color}66`, color, boxShadow: root ? `0 0 16px ${color}55` : undefined }}
        title={node.hash}
      >
        {root ? "ROOT " : ""}{shortHash(node.hash, 6, 4)}
      </motion.div>
      {node.children && node.children.length > 0 && (
        <>
          <div className="h-4 w-px bg-white/15" />
          <div className="flex gap-4">
            {node.children.map((c, i) => (
              <div key={i} className="flex flex-col items-center">
                <TreeNode node={c} depth={depth + 1} />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function MerkleTree() {
  const { data } = useBlockchain();
  const merkle = useMerkleRoot();
  const [tree, setTree] = useState<MNode | null>(null);
  const [leaves, setLeaves] = useState<string[]>([]);

  useEffect(() => {
    const recent = (data?.chain ?? []).slice(-8).map((b) => b.hash);
    setLeaves(recent);
    buildMerkle(recent).then(setTree);
  }, [data?.chain]);

  return (
    <div className="space-y-4">
      <GlassCard>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-signal-violet/15 ring-1 ring-signal-violet/30">
              <GitBranch className="h-5 w-5 text-signal-violet" />
            </div>
            <div>
              <p className="font-display text-lg font-bold text-white">Merkle Tree Visualization</p>
              <p className="font-mono text-[11px] text-white/45">Built live (Web Crypto SHA-256) over the last {leaves.length} block hashes</p>
            </div>
          </div>
          <div className="rounded-xl border border-signal-green/30 bg-signal-green/5 px-4 py-2">
            <p className="hud-label">Ledger Merkle Root</p>
            <p className="font-mono text-xs text-signal-green">{shortHash(merkle.data?.merkle_root, 10, 8)}</p>
          </div>
        </div>
      </GlassCard>

      <GlassCard className="!p-6">
        <SectionTitle>Tree</SectionTitle>
        <div className="flex justify-center overflow-x-auto pb-4">
          {tree ? (
            <div className="flex flex-col items-center gap-1">
              <TreeNode node={tree} depth={0} root />
            </div>
          ) : (
            <p className="py-10 font-mono text-[11px] text-white/30 flex items-center gap-2"><RefreshCw className="h-4 w-4 animate-spin" /> hashing leaves…</p>
          )}
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-4 font-mono text-[10px] text-white/50">
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-signal-green" /> Root</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-signal-violet" /> Intermediate</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-cyber-400" /> Leaf (block hash)</span>
        </div>
      </GlassCard>
    </div>
  );
}
