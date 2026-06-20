import { NavLink } from "react-router-dom";
import { motion } from "framer-motion";
import { ShieldCheck, X } from "lucide-react";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";

const groups = Array.from(new Set(NAV.map((n) => n.group)));

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      {/* mobile overlay */}
      {open && (
        <div className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden" onClick={onClose} />
      )}
      <aside
        className={cn(
          "panel fixed z-40 flex h-full w-64 flex-col rounded-r-2xl transition-transform duration-300 lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between gap-2 px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="relative grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-cyber-500/30 to-cyan-glow/20 ring-1 ring-cyan-glow/30">
              <ShieldCheck className="h-5 w-5 text-cyan-glow" />
              <span className="absolute inset-0 animate-pulse-glow rounded-xl ring-1 ring-cyan-glow/20" />
            </div>
            <div className="leading-tight">
              <p className="font-display text-sm font-bold tracking-wider text-white">POSEVISION</p>
              <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-cyber-400/70">
                Edge · C2
              </p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1 text-white/40 hover:bg-white/5 lg:hidden">
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 pb-4">
          {groups.map((group) => (
            <div key={group} className="mb-4">
              <p className="px-3 pb-2 font-mono text-[9px] uppercase tracking-[0.3em] text-white/25">
                {group}
              </p>
              <div className="space-y-1">
                {NAV.filter((n) => n.group === group).map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === "/"}
                    onClick={onClose}
                    className={({ isActive }) =>
                      cn(
                        "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all",
                        isActive
                          ? "bg-cyan-glow/10 text-white"
                          : "text-white/55 hover:bg-white/[0.04] hover:text-white/90",
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <motion.span
                            layoutId="nav-active"
                            className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r bg-cyan-glow shadow-glow-sm"
                          />
                        )}
                        <item.icon className={cn("h-4 w-4", isActive && "text-cyan-glow")} />
                        <span className="font-medium">{item.label}</span>
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-white/5 px-5 py-3">
          <p className="font-mono text-[9px] leading-relaxed text-white/30">
            PRIVACY-PRESERVING EDGE AI
            <br />
            BLOCKCHAIN TAMPER-EVIDENT LOG
          </p>
        </div>
      </aside>
    </>
  );
}
