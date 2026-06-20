import { useMemo, useState } from "react";
import { FileText, FileJson, FileSpreadsheet, Printer, Calendar } from "lucide-react";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { useBlockchain } from "@/hooks/useApiData";
import { useChainMetrics } from "@/hooks/useChainMetrics";
import { eventLabel, fmtDateTime } from "@/lib/utils";
import type { Block } from "@/lib/types";

function download(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export default function Reports() {
  const { data } = useBlockchain();
  const m = useChainMetrics();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const rows = useMemo(() => {
    let chain: Block[] = data?.chain ?? [];
    if (from) chain = chain.filter((b) => new Date(b.timestamp) >= new Date(from));
    if (to) chain = chain.filter((b) => new Date(b.timestamp) <= new Date(to + "T23:59:59"));
    return chain;
  }, [data, from, to]);

  function exportJson() {
    download(`posevision-report-${Date.now()}.json`, JSON.stringify({ generated: new Date().toISOString(), metrics: m, events: rows }, null, 2), "application/json");
  }
  function exportCsv() {
    const header = "index,timestamp,event,person_id,zone,authorized,hash,merkle_root,ipfs_cid";
    const lines = rows.map((b) => {
      const e = b.event;
      return [b.index, b.timestamp, e?.alert_type || e?.type, e?.person_id ?? "", e?.access?.zone ?? "", e?.access?.authorized ?? "", b.hash, b.merkle_root, b.ipfs_cid].join(",");
    });
    download(`posevision-report-${Date.now()}.csv`, [header, ...lines].join("\n"), "text/csv");
  }

  return (
    <div className="space-y-4">
      <GlassCard>
        <SectionTitle>Compliance &amp; Audit Report</SectionTitle>
        <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Cell label="Events in range" value={String(rows.length)} />
            <Cell label="Helmet compliance" value={`${m.helmetOn + m.helmetOff ? Math.round((m.helmetOn / (m.helmetOn + m.helmetOff)) * 100) : 100}%`} />
            <Cell label="Intrusions" value={String(m.intrusions)} />
            <Cell label="Tamper alerts" value={String(m.tamperAlerts)} />
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <p className="hud-label mb-1 flex items-center gap-1"><Calendar className="h-3 w-3" /> From</p>
              <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="rounded-lg border border-white/10 bg-black/40 px-2 py-1.5 font-mono text-xs text-white" />
            </div>
            <div>
              <p className="hud-label mb-1">To</p>
              <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="rounded-lg border border-white/10 bg-black/40 px-2 py-1.5 font-mono text-xs text-white" />
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Btn onClick={exportCsv} icon={FileSpreadsheet} label="Export CSV" color="text-signal-green border-signal-green/40 bg-signal-green/10" />
          <Btn onClick={exportJson} icon={FileJson} label="Export JSON" color="text-cyber-400 border-cyber-400/40 bg-cyber-400/10" />
          <Btn onClick={() => window.print()} icon={Printer} label="Print / PDF" color="text-signal-violet border-signal-violet/40 bg-signal-violet/10" />
        </div>
      </GlassCard>

      <GlassCard>
        <SectionTitle><span className="flex items-center gap-2"><FileText className="h-3.5 w-3.5" /> Event Ledger ({rows.length})</span></SectionTitle>
        <div className="max-h-[440px] overflow-auto">
          <table className="w-full text-left font-mono text-[11px]">
            <thead className="sticky top-0 bg-navy-900/95 text-white/40">
              <tr className="[&>th]:px-2 [&>th]:py-2 [&>th]:font-medium">
                <th>#</th><th>Time</th><th>Event</th><th>Person</th><th>Zone</th><th>Hash</th>
              </tr>
            </thead>
            <tbody className="text-white/70">
              {rows.slice().reverse().map((b) => (
                <tr key={b.index} className="border-t border-white/5 [&>td]:px-2 [&>td]:py-1.5">
                  <td className="text-cyber-400">{b.index}</td>
                  <td>{fmtDateTime(b.timestamp)}</td>
                  <td>{eventLabel(b.event?.alert_type || b.event?.type)}</td>
                  <td>{b.event?.person_id ?? "—"}</td>
                  <td>{b.event?.access?.zone ?? "—"}</td>
                  <td className="text-white/40">{b.hash.slice(0, 12)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  );
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02] p-3">
      <p className="hud-label">{label}</p>
      <p className="mt-1 font-display text-xl font-bold text-white">{value}</p>
    </div>
  );
}
function Btn({ onClick, icon: Icon, label, color }: { onClick: () => void; icon: typeof FileText; label: string; color: string }) {
  return (
    <button onClick={onClick} className={`flex items-center gap-2 rounded-lg border px-3 py-2 font-mono text-xs uppercase tracking-wider ${color}`}>
      <Icon className="h-3.5 w-3.5" /> {label}
    </button>
  );
}
