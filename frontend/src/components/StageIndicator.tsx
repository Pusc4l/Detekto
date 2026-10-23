"use client";

import { motion } from "framer-motion";
import type { Stage } from "@/lib/types";

interface StageIndicatorProps {
  stage: Stage;
  canEnterStage2: boolean;
  onSelect: (stage: Stage) => void;
}

const STAGES: ReadonlyArray<{ id: Stage; code: string; label: string }> = [
  { id: 1, code: "01", label: "CONTEXT LOCK" },
  { id: 2, code: "02", label: "TARGET EVIDENCE" },
];

export function StageIndicator({ stage, canEnterStage2, onSelect }: StageIndicatorProps) {
  return (
    <nav aria-label="Tahap interogasi" className="grid grid-cols-2 gap-0 border-8 border-ink shadow-brutal">
      {STAGES.map((s) => {
        const active = stage === s.id;
        const locked = s.id === 2 && !canEnterStage2;
        return (
          <motion.button
            key={s.id}
            type="button"
            disabled={locked}
            aria-current={active ? "step" : undefined}
            onClick={() => onSelect(s.id)}
            whileTap={locked ? undefined : { scale: 0.97 }}
            transition={{ type: "spring", stiffness: 900, damping: 40 }}
            className={`flex items-center gap-3 rounded-none border-ink p-3 text-left disabled:cursor-not-allowed ${
              s.id === 1 ? "border-r-4" : "border-l-4"
            } ${active ? "bg-ink text-acid" : locked ? "bg-concrete text-ink" : "bg-canvas text-ink"}`}
          >
            <span className="font-display text-4xl font-bold leading-none">{s.code}</span>
            <span className="font-display text-lg font-bold uppercase leading-tight">
              {s.label}
              {locked && <span className="block font-mono text-[10px]">TERKUNCI — LENGKAPI TAHAP 01</span>}
            </span>
          </motion.button>
        );
      })}
    </nav>
  );
}
