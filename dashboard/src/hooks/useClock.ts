import { useEffect, useState, useRef } from "react";

/** Ticking clock (UTC + local) for the command-center header. */
export function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return now;
}

/** Mission elapsed timer (since the dashboard session began). */
export function useMissionTimer() {
  const start = useRef(Date.now());
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setElapsed(Date.now() - start.current), 1000);
    return () => window.clearInterval(id);
  }, []);
  const total = Math.floor(elapsed / 1000);
  const h = String(Math.floor(total / 3600)).padStart(2, "0");
  const m = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const s = String(total % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}
