"use client";

import { useEffect } from "react";
import { AnimatePresence, motion, type Variants } from "framer-motion";
import { ContextLockPanel } from "@/components/ContextLockPanel";
import { EvidencePanel } from "@/components/EvidencePanel";
import { StageIndicator } from "@/components/StageIndicator";
import { canLockContext, useInterrogationStore } from "@/store/useInterrogationStore";
import type { Stage } from "@/lib/types";

/** Transisi layar mekanis: panel digeser horizontal ala pintu geser baja (tween pendek, tanpa fade lembut). */
const SLIDE: Variants = {
  enter: (stage: Stage) => ({ x: stage === 2 ? 140 : -140 }),
  center: { x: 0 },
  exit: (stage: Stage) => ({ x: stage === 2 ? -140 : 140 }),
};

export function InterrogationRoom() {
  const stage = useInterrogationStore((s) => s.stage);
  const setStage = useInterrogationStore((s) => s.setStage);
  const canEnterStage2 = useInterrogationStore((s) => canLockContext(s));

  // Drop di luar dropzone akan membuat browser/WebView menavigasi ke file gambar -> state hilang. Cegah.
  useEffect(() => {
    const block = (e: DragEvent) => e.preventDefault();
    window.addEventListener("dragover", block);
    window.addEventListener("drop", block);
    return () => {
      window.removeEventListener("dragover", block);
      window.removeEventListener("drop", block);
    };
  }, []);

  return (
    <section className="flex flex-col gap-6" aria-label="Ruang interogasi">
      <StageIndicator stage={stage} canEnterStage2={canEnterStage2} onSelect={setStage} />
      <div className="overflow-x-clip pb-4 pr-4">
        <AnimatePresence mode="wait" initial={false} custom={stage}>
          <motion.div
            key={stage}
            custom={stage}
            variants={SLIDE}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.16, ease: [0.7, 0, 0.3, 1] }}
          >
            {stage === 1 ? <ContextLockPanel /> : <EvidencePanel />}
          </motion.div>
        </AnimatePresence>
      </div>
    </section>
  );
}
