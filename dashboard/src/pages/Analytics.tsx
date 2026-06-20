import {
  AreaChart, Area, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadialBarChart, RadialBar,
} from "recharts";
import { GlassCard, SectionTitle } from "@/components/ui/GlassCard";
import { useChainMetrics } from "@/hooks/useChainMetrics";
import { eventLabel } from "@/lib/utils";

const COLORS = ["#22d3ee", "#22e3a0", "#f5b73d", "#ff4d61", "#a78bfa", "#38bdf8"];

const tooltipStyle = {
  background: "rgba(7,13,28,0.95)",
  border: "1px solid rgba(34,211,238,0.3)",
  borderRadius: 10,
  fontFamily: "JetBrains Mono",
  fontSize: 11,
  color: "#fff",
};

export default function Analytics() {
  const m = useChainMetrics();

  const typeData = Object.entries(m.byType)
    .filter(([k]) => k !== "GENESIS")
    .map(([k, v]) => ({ name: eventLabel(k), value: v }));

  const compliance = [
    { name: "Helmet", on: m.helmetOn, off: m.helmetOff },
    { name: "Vest", on: m.vestOn, off: m.vestOff },
  ];

  const accessData = [
    { name: "Authorized", value: m.authorized, fill: "#22e3a0" },
    { name: "Unauthorized", value: m.unauthorized, fill: "#ff4d61" },
    { name: "Unknown RFID", value: m.unknownRfid, fill: "#f5b73d" },
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <GlassCard>
          <SectionTitle>Alerts by Hour (24h)</SectionTitle>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={m.hourly}>
              <defs>
                <linearGradient id="alerts" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.6} />
                  <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="intr" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ff4d61" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#ff4d61" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="hour" tick={{ fill: "#8aa", fontSize: 9 }} interval={3} />
              <YAxis tick={{ fill: "#8aa", fontSize: 9 }} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="alerts" stroke="#22d3ee" fill="url(#alerts)" strokeWidth={2} />
              <Area type="monotone" dataKey="intrusions" stroke="#ff4d61" fill="url(#intr)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </GlassCard>

        <GlassCard>
          <SectionTitle>PPE Compliance</SectionTitle>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={compliance} barGap={8}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="name" tick={{ fill: "#8aa", fontSize: 11 }} />
              <YAxis tick={{ fill: "#8aa", fontSize: 9 }} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="on" name="Compliant" fill="#22e3a0" radius={[4, 4, 0, 0]} />
              <Bar dataKey="off" name="Violation" fill="#ff4d61" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <GlassCard>
          <SectionTitle>Event Distribution</SectionTitle>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={typeData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={85} paddingAngle={3}>
                {typeData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
        </GlassCard>

        <GlassCard>
          <SectionTitle>RFID Access Outcomes</SectionTitle>
          <ResponsiveContainer width="100%" height={240}>
            <RadialBarChart innerRadius="30%" outerRadius="100%" data={accessData} startAngle={90} endAngle={-270}>
              <RadialBar background dataKey="value" cornerRadius={6} />
              <Tooltip contentStyle={tooltipStyle} />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-3 font-mono text-[10px]">
            {accessData.map((a) => (
              <span key={a.name} className="flex items-center gap-1 text-white/50">
                <span className="h-2 w-2 rounded-full" style={{ background: a.fill }} /> {a.name}
              </span>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle>Ledger Growth</SectionTitle>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={m.hourly}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="hour" tick={{ fill: "#8aa", fontSize: 9 }} interval={5} />
              <YAxis tick={{ fill: "#8aa", fontSize: 9 }} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="access" name="Access" stroke="#22e3a0" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="alerts" name="Alerts" stroke="#a78bfa" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </GlassCard>
      </div>
    </div>
  );
}
