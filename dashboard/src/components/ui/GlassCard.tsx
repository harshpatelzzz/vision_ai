import { forwardRef, type HTMLAttributes } from "react";
import { motion, type HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/utils";

interface GlassCardProps extends HTMLMotionProps<"div"> {
  reticle?: boolean;
  glow?: boolean;
}

export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, reticle, glow, children, ...props }, ref) => (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "glass glass-hover p-4",
        reticle && "reticle",
        glow && "shadow-glow",
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  ),
);
GlassCard.displayName = "GlassCard";

export function SectionTitle({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("mb-3 flex items-center gap-2", className)} {...props}>
      <span className="h-3 w-1 rounded-full bg-cyan-glow shadow-glow-sm" />
      <h2 className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-white/90">
        {children}
      </h2>
    </div>
  );
}
