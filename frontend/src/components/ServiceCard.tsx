"use client";

import { motion } from "framer-motion";
import type { ServiceState, ServiceStatus } from "@/lib/types";

const SURFACE: Record<ServiceState, string> = {
  primary: "bg-radar text-ink",
  fallback: "bg-acid text-ink",
  down: "bg-crimson text-canvas",
};

const LABEL: Record<ServiceState, string> = {
  primary: "PRIMARY",
  fallback: "FALLBACK",
  down: "DOWN",
};

export function ServiceCard({ service, index }: { service: ServiceStatus; index: number }) {
  return (
    <motion.li
      initial={{ y: -70, rotate: -3 }}
      animate={{ y: 0, rotate: 0 }}
      transition={{ type: "spring", stiffness: 420, damping: 26, delay: index * 0.07 }}
      className={`flex flex-col gap-3 rounded-none border-4 border-ink p-4 shadow-brutal ${SURFACE[service.state]}`}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-lg font-bold uppercase leading-tight">{service.label}</h3>
        <span
          aria-hidden
          className="mt-1 h-5 w-5 shrink-0 rounded-full border-4 border-ink bg-canvas"
        />
      </div>
      <div className="flex flex-wrap items-center gap-2 font-mono text-xs font-bold uppercase">
        <span className="rounded-none border-4 border-ink bg-ink px-2 py-1 text-canvas">{LABEL[service.state]}</span>
        <span className="rounded-none border-4 border-ink bg-canvas px-2 py-1 text-ink">{service.mode}</span>
        {service.latency_ms !== null && (
          <span className="rounded-none border-4 border-ink bg-canvas px-2 py-1 text-ink">{service.latency_ms} MS</span>
        )}
      </div>
      <p className="border-t-4 border-ink pt-3 font-mono text-xs font-bold leading-relaxed">{service.detail}</p>
    </motion.li>
  );
}
