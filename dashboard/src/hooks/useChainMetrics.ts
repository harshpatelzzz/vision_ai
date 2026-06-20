import { useMemo } from "react";
import { useBlockchain } from "./useApiData";
import type { Block } from "@/lib/types";

export interface ChainMetrics {
  height: number;
  persons: number;
  helmetOn: number;
  helmetOff: number;
  vestOn: number;
  vestOff: number;
  intrusions: number;
  authorized: number;
  unauthorized: number;
  unknownRfid: number;
  tamperAlerts: number;
  todaysAlerts: number;
  byType: Record<string, number>;
  hourly: { hour: string; alerts: number; intrusions: number; access: number }[];
  recent: Block[];
  loading: boolean;
  error: boolean;
}

const isAlert = (t: string) =>
  ["NO_HELMET", "NO_VEST", "INTRUSION", "FALL_DETECTED", "TAMPER_DETECTED", "UNAUTHORIZED_INTRUSION", "ZONE_VIOLATION", "UNKNOWN_RFID", "ACCESS_DENIED"].includes(t);

export function useChainMetrics(): ChainMetrics {
  const q = useBlockchain();
  const chain = q.data?.chain ?? [];

  return useMemo(() => {
    const byType: Record<string, number> = {};
    const persons = new Set<number>();
    let helmetOn = 0, helmetOff = 0, vestOn = 0, vestOff = 0;
    let intrusions = 0, authorized = 0, unauthorized = 0, unknownRfid = 0, tamperAlerts = 0, todaysAlerts = 0;

    const today = new Date().toDateString();
    const hourMap = new Map<number, { alerts: number; intrusions: number; access: number }>();
    for (let h = 0; h < 24; h++) hourMap.set(h, { alerts: 0, intrusions: 0, access: 0 });

    for (const b of chain) {
      const ev = b.event || ({} as Block["event"]);
      const type = ev.alert_type || ev.type || "EVENT";
      byType[type] = (byType[type] || 0) + 1;
      if (typeof ev.person_id === "number" && ev.person_id >= 0) persons.add(ev.person_id);

      if (ev.ppe) {
        if (ev.ppe.helmet) helmetOn++; else helmetOff++;
        if (ev.ppe.vest) vestOn++; else vestOff++;
      }
      if (ev.intrusion) intrusions++;
      if (type === "AUTHORIZED_ACCESS") authorized++;
      if (["UNAUTHORIZED_INTRUSION", "ZONE_VIOLATION", "ACCESS_DENIED"].includes(type)) unauthorized++;
      if (type === "UNKNOWN_RFID") unknownRfid++;
      if (type === "TAMPER_DETECTED") tamperAlerts++;

      const d = new Date(b.timestamp);
      if (!Number.isNaN(d.getTime())) {
        if (d.toDateString() === today && isAlert(type)) todaysAlerts++;
        const slot = hourMap.get(d.getHours());
        if (slot) {
          if (isAlert(type)) slot.alerts++;
          if (ev.intrusion) slot.intrusions++;
          if (type === "AUTHORIZED_ACCESS") slot.access++;
        }
      }
    }

    const hourly = Array.from(hourMap.entries()).map(([h, v]) => ({
      hour: `${String(h).padStart(2, "0")}:00`,
      ...v,
    }));

    return {
      height: q.data?.height ?? chain.length,
      persons: persons.size,
      helmetOn, helmetOff, vestOn, vestOff,
      intrusions, authorized, unauthorized, unknownRfid, tamperAlerts, todaysAlerts,
      byType,
      hourly,
      recent: [...chain].reverse().slice(0, 30),
      loading: q.isLoading,
      error: q.isError,
    };
  }, [chain, q.data?.height, q.isLoading, q.isError]);
}
