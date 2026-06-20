import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Sidebar } from "./Sidebar";
import { TopHeader } from "./TopHeader";
import { NotificationPanel } from "./NotificationPanel";
import { LiveLogConsole } from "./LiveLogConsole";
import { TelemetryBridge } from "./TelemetryBridge";

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const location = useLocation();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-void bg-grid">
      <TelemetryBridge />
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader
          onMenu={() => setSidebarOpen(true)}
          onToggleNotifications={() => setNotifOpen((o) => !o)}
        />

        <main className="relative flex-1 overflow-y-auto px-4 py-4 sm:px-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto max-w-[1600px]"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>

        <LiveLogConsole />
      </div>

      <NotificationPanel open={notifOpen} onClose={() => setNotifOpen(false)} />
    </div>
  );
}
