import { useEffect, useRef, useState, useCallback } from "react";
import { wsUrl } from "@/lib/api";

export type WsStatus = "connecting" | "open" | "closed" | "error";

interface Options<T> {
  /** WS path, e.g. "/ws/telemetry" (proxied in dev). */
  path: string;
  enabled?: boolean;
  onMessage?: (data: T) => void;
  reconnectMs?: number;
}

/**
 * Auto-reconnecting JSON WebSocket. Survives backend restarts and ESP32 drops —
 * exposes a stable `status` for "beautiful error states".
 */
export function useWebSocket<T = unknown>({
  path,
  enabled = true,
  onMessage,
  reconnectMs = 2500,
}: Options<T>) {
  const [status, setStatus] = useState<WsStatus>("connecting");
  const [last, setLast] = useState<T | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<number | null>(null);
  const stopped = useRef(false);
  const cbRef = useRef(onMessage);
  cbRef.current = onMessage;

  const connect = useCallback(() => {
    if (stopped.current) return;
    try {
      setStatus("connecting");
      const ws = new WebSocket(wsUrl(path));
      wsRef.current = ws;

      ws.onopen = () => setStatus("open");
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as T;
          setLast(data);
          cbRef.current?.(data);
        } catch {
          /* ignore non-JSON frames */
        }
      };
      ws.onerror = () => setStatus("error");
      ws.onclose = () => {
        setStatus("closed");
        if (!stopped.current) {
          timerRef.current = window.setTimeout(connect, reconnectMs);
        }
      };
    } catch {
      setStatus("error");
      timerRef.current = window.setTimeout(connect, reconnectMs);
    }
  }, [path, reconnectMs]);

  useEffect(() => {
    stopped.current = false;
    if (enabled) connect();
    return () => {
      stopped.current = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [enabled, connect]);

  const send = useCallback((payload: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof payload === "string" ? payload : JSON.stringify(payload));
    }
  }, []);

  return { status, last, send };
}
