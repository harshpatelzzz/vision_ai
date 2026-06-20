import { useEffect, useRef } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { WS_PATHS } from "@/lib/api";
import { useBlockchain, useRfidAccessLog, useSecurityStatus } from "@/hooks/useApiData";
import { useSystem } from "@/store/SystemContext";
import { eventLabel, severityForEvent } from "@/lib/utils";
import type { AccessBlock, SensorSnapshot } from "@/lib/types";

/**
 * Invisible component: bridges real backend data (WS telemetry + polled REST)
 * into the global log console and notification system. Mounted once in AppShell.
 */
export function TelemetryBridge() {
  const { pushLog, pushNotification } = useSystem();

  // ---- ESP32 / hardware telemetry over WebSocket ----
  const tamperLatch = useRef(false);
  useWebSocket<{ telemetry: SensorSnapshot; stream_url?: string }>({
    path: WS_PATHS.telemetry,
    onMessage: (data) => {
      const t = data?.telemetry;
      if (!t || Object.keys(t).length === 0) return;
      if (t._connected) {
        pushLog({
          source: "ESP32",
          level: "info",
          message: `temp=${t.temperature ?? "?"}C dist=${t.distance ?? "?"}mm light=${t.light ?? "?"} wifi=${t.wifi ? "up" : "down"}`,
        });
      }
      if (t.tamper && !tamperLatch.current) {
        tamperLatch.current = true;
        pushLog({ source: "TAMPER", level: "critical", message: "ESP32 enclosure tamper signal asserted" });
        pushNotification({
          title: "Tamper Detected",
          message: "ESP32 sensor enclosure integrity breach.",
          severity: "critical",
        });
      }
      if (!t.tamper) tamperLatch.current = false;
    },
  });

  // ---- Blockchain growth ----
  const chain = useBlockchain();
  const lastHeight = useRef<number | null>(null);
  useEffect(() => {
    const h = chain.data?.height;
    if (h == null) return;
    if (lastHeight.current == null) {
      lastHeight.current = h;
      pushLog({ source: "BLOCKCHAIN", level: "success", message: `chain synced · height=${h}` });
      return;
    }
    if (h > lastHeight.current) {
      const tip = chain.data?.chain?.[chain.data.chain.length - 1];
      const evType = tip?.event?.alert_type || tip?.event?.type || "EVENT";
      pushLog({
        source: "BLOCKCHAIN",
        level: "success",
        message: `block #${h - 1} sealed · ${evType} · merkle=${tip?.merkle_root?.slice(0, 10)}…`,
      });
      lastHeight.current = h;
    }
    if (chain.data?.validation?.status === "tampered") {
      pushNotification({
        title: "Blockchain Failure",
        message: `Ledger tampered at block ${chain.data.validation.corrupt_index}.`,
        severity: "critical",
      });
    }
  }, [chain.data, pushLog, pushNotification]);

  // ---- RFID access decisions ----
  const rfid = useRfidAccessLog(50);
  const seen = useRef<Set<string>>(new Set());
  const primed = useRef(false);
  useEffect(() => {
    const events = rfid.data?.events;
    if (!events) return;
    events.forEach((e: AccessBlock) => {
      const key = `${e.timestamp}:${e.uid}:${e.event_type}`;
      if (seen.current.has(key)) return;
      seen.current.add(key);
      if (!primed.current) return; // skip historical backlog on first load
      const sev = severityForEvent(e.event_type);
      pushLog({
        source: "RFID",
        level: sev,
        message: `${e.event_type} · uid=${e.uid ?? "—"} · ${e.name ?? "Unknown"} · ${e.zone ?? "?"}`,
      });
      if (sev === "critical" || sev === "warning") {
        pushNotification({
          title: eventLabel(e.event_type),
          message: `${e.name ?? "Unknown tag"} @ ${e.zone ?? "?"} — ${e.reason}`,
          severity: sev,
        });
      }
    });
    primed.current = true;
  }, [rfid.data, pushLog, pushNotification]);

  // ---- Hardware monitor tamper ----
  const sec = useSecurityStatus();
  const secLatch = useRef(false);
  useEffect(() => {
    const t = sec.data?.tamper_detected;
    if (t && !secLatch.current) {
      secLatch.current = true;
      pushNotification({
        title: "Hardware Tamper",
        message: "GPIO/serial tamper line triggered on the edge node.",
        severity: "critical",
      });
      pushLog({ source: "HARDWARE", level: "critical", message: "hardware monitor: TAMPER_DETECTED" });
    }
    if (!t) secLatch.current = false;
  }, [sec.data, pushLog, pushNotification]);

  return null;
}
