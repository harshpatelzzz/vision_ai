import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { AppNotification, LogLine, Severity } from "@/lib/types";
import { uid } from "@/lib/utils";

interface SystemState {
  notifications: AppNotification[];
  logs: LogLine[];
  pushNotification: (n: Omit<AppNotification, "id" | "ts">) => void;
  dismissNotification: (id: string) => void;
  markAllRead: () => void;
  clearNotifications: () => void;
  pushLog: (l: Omit<LogLine, "id" | "ts">) => void;
  clearLogs: () => void;
}

const SystemCtx = createContext<SystemState | null>(null);
const MAX_LOGS = 400;
const MAX_NOTIFS = 60;

export function SystemProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [logs, setLogs] = useState<LogLine[]>([]);
  // de-dupe identical toasts fired in quick succession
  const lastKey = useRef<Record<string, number>>({});

  const pushNotification = useCallback((n: Omit<AppNotification, "id" | "ts">) => {
    const key = `${n.severity}:${n.title}:${n.message}`;
    const now = Date.now();
    if (lastKey.current[key] && now - lastKey.current[key] < 4000) return;
    lastKey.current[key] = now;
    setNotifications((prev) => [{ ...n, id: uid(), ts: now }, ...prev].slice(0, MAX_NOTIFS));
  }, []);

  const dismissNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const markAllRead = useCallback(
    () => setNotifications((prev) => prev.map((n) => ({ ...n, read: true }))),
    [],
  );
  const clearNotifications = useCallback(() => setNotifications([]), []);

  const pushLog = useCallback((l: Omit<LogLine, "id" | "ts">) => {
    setLogs((prev) => [...prev, { ...l, id: uid(), ts: Date.now() }].slice(-MAX_LOGS));
  }, []);
  const clearLogs = useCallback(() => setLogs([]), []);

  const value = useMemo(
    () => ({
      notifications,
      logs,
      pushNotification,
      dismissNotification,
      markAllRead,
      clearNotifications,
      pushLog,
      clearLogs,
    }),
    [notifications, logs, pushNotification, dismissNotification, markAllRead, clearNotifications, pushLog, clearLogs],
  );

  return <SystemCtx.Provider value={value}>{children}</SystemCtx.Provider>;
}

export function useSystem(): SystemState {
  const ctx = useContext(SystemCtx);
  if (!ctx) throw new Error("useSystem must be used within SystemProvider");
  return ctx;
}

/** Helper to derive a global threat level from booleans. */
export function deriveThreatLevel(opts: {
  tamper?: boolean;
  chainTampered?: boolean;
  unauthorized?: number;
  sensorTamper?: boolean;
}): { level: "NOMINAL" | "ELEVATED" | "CRITICAL"; score: number; color: Severity } {
  let score = 0;
  if (opts.tamper) score += 3;
  if (opts.chainTampered) score += 3;
  if (opts.sensorTamper) score += 2;
  if (opts.unauthorized && opts.unauthorized > 0) score += Math.min(2, opts.unauthorized);
  if (score >= 3) return { level: "CRITICAL", score, color: "critical" };
  if (score >= 1) return { level: "ELEVATED", score, color: "warning" };
  return { level: "NOMINAL", score, color: "success" };
}
