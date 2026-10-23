"use client";

import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { BrutalButton } from "@/components/BrutalButton";
import { useInterrogationStore } from "@/store/useInterrogationStore";
import type { Notice, NoticeTone } from "@/lib/types";

const AUTO_DISMISS_MS = 7000;

const SURFACE: Record<NoticeTone, string> = {
  error: "bg-crimson text-canvas",
  warn: "bg-hazard text-ink",
  info: "bg-acid text-ink",
};

const HEADING: Record<NoticeTone, string> = {
  error: "DITOLAK",
  warn: "PERINGATAN",
  info: "INFO",
};

function NoticeItem({ notice }: { notice: Notice }) {
  const dismiss = useInterrogationStore((s) => s.dismissNotice);

  useEffect(() => {
    const timer = window.setTimeout(() => dismiss(notice.id), AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [dismiss, notice.id]);

  return (
    <motion.li
      layout
      initial={{ x: 140 }}
      animate={{ x: 0 }}
      exit={{ x: 140 }}
      transition={{ type: "spring", stiffness: 700, damping: 38 }}
      className={`flex items-start justify-between gap-3 rounded-none border-8 border-ink p-3 shadow-brutal ${SURFACE[notice.tone]}`}
    >
      <div>
        <p className="font-display text-lg font-bold uppercase leading-none">{HEADING[notice.tone]}</p>
        <p className="mt-1 break-words font-mono text-xs font-bold uppercase">{notice.text}</p>
      </div>
      <BrutalButton size="sm" tone="canvas" aria-label="Tutup notifikasi" onClick={() => dismiss(notice.id)}>
        X
      </BrutalButton>
    </motion.li>
  );
}

export function NoticeStack() {
  const notices = useInterrogationStore((s) => s.notices);
  return (
    <ul
      role="alert"
      aria-live="assertive"
      className="pointer-events-none fixed bottom-6 right-6 z-50 flex w-[min(92vw,26rem)] flex-col gap-4 [&>li]:pointer-events-auto"
    >
      <AnimatePresence initial={false}>
        {notices.map((n) => (
          <NoticeItem key={n.id} notice={n} />
        ))}
      </AnimatePresence>
    </ul>
  );
}
