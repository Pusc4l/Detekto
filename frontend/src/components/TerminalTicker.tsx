"use client";

import { useEffect, useRef } from "react";
import type { LogEvent, LogLevel } from "@/lib/types";

const LEVEL_COLOR: Record<LogLevel, string> = {
  SYS: "text-acid",
  INFO: "text-canvas",
  OK: "text-radar",
  WARN: "text-hazard",
  ERROR: "text-crimson",
};

const timeOf = (ts: string): string => (ts.length >= 19 ? ts.slice(11, 19) : "--:--:--");

/** Live Terminal Log Ticker. Semua teks dirender sebagai text node React (tanpa injeksi HTML mentah). */
export function TerminalTicker({ logs, live }: { logs: LogEvent[]; live: boolean }) {
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = boxRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [logs.length]);

  return (
    <section className="rounded-none border-8 border-ink bg-ink shadow-brutal" aria-label="Terminal log">
      <div className="flex items-center justify-between border-b-8 border-ink bg-acid px-4 py-2">
        <h2 className="font-display text-xl font-bold uppercase text-ink">LIVE TERMINAL // /ws/interrogation</h2>
        <span className="font-mono text-xs font-bold uppercase text-ink">{live ? "STREAMING" : "OFFLINE"}</span>
      </div>
      <div className={`h-4 border-b-8 border-ink hazard-stripes ${live ? "animate-stripes" : ""}`} />
      <div ref={boxRef} className="h-72 overflow-y-auto p-4 font-mono text-sm" role="log" aria-live="polite">
        {logs.length === 0 && <p className="text-canvas">&gt; MENUNGGU TRANSMISI...</p>}
        {logs.map((ev, i) => (
          <p key={`${ev.ts}-${i}`} className={`break-words ${LEVEL_COLOR[ev.level]}`}>
            <span className="text-concrete">[{timeOf(ev.ts)}]</span> <span className="font-bold">{ev.level.padEnd(5, " ")}</span>{" "}
            <span className="font-bold">{ev.source}</span> &gt; {ev.message}
          </p>
        ))}
      </div>
    </section>
  );
}
