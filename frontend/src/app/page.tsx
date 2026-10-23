"use client";

import { useBackendLink } from "@/hooks/useBackendLink";
import { useInterrogationStore } from "@/store/useInterrogationStore";
import { useSystemStore } from "@/store/useSystemStore";
import { AnalysisResultPanel } from "@/components/AnalysisResultPanel";
import { BrutalButton } from "@/components/BrutalButton";
import { CommandCenter } from "@/components/CommandCenter";
import { InterrogationRoom } from "@/components/InterrogationRoom";
import { NoticeStack } from "@/components/NoticeStack";
import { SwarmPanel } from "@/components/SwarmPanel";
import { ServiceCard } from "@/components/ServiceCard";
import { VerdictPanel } from "@/components/VerdictPanel";
import { TerminalTicker } from "@/components/TerminalTicker";

function StatBlock({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className={`rounded-none border-8 border-ink p-4 shadow-brutal ${tone}`}>
      <p className="font-mono text-xs font-bold uppercase">{label}</p>
      <p className="font-display text-3xl font-bold uppercase leading-none">{value}</p>
    </div>
  );
}

export default function HomePage() {
  const { refresh, ping } = useBackendLink();
  const health = useSystemStore((s) => s.health);
  const backendReachable = useSystemStore((s) => s.backendReachable);
  const scanning = useSystemStore((s) => s.scanning);
  const wsState = useSystemStore((s) => s.wsState);
  const logs = useSystemStore((s) => s.logs);
  const loadStress = useInterrogationStore((s) => s.loadStressGraph);
  const graphBusy = useInterrogationStore((s) => s.graph.status === "working");

  const wsTone =
    wsState === "OPEN" ? "bg-radar text-ink" : wsState === "CONNECTING" ? "bg-acid text-ink" : "bg-crimson text-canvas";
  const summary = health
    ? `${health.primary_count} PRIMARY / ${health.fallback_count} FALLBACK / ${health.down_count} DOWN`
    : "BELUM ADA DATA";

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-10 p-6 md:p-10">
      <header className="rounded-none border-8 border-ink bg-acid p-6 shadow-brutal">
        <p className="font-mono text-sm font-bold uppercase">PHASE 6 // COMMAND CENTER</p>
        <h1 className="font-display text-6xl font-bold uppercase leading-none tracking-tighter md:text-8xl">DETEKTO</h1>
        <p className="mt-3 border-t-8 border-ink pt-3 font-mono text-sm font-bold uppercase">
          DECENTRALIZED OSINT &amp; CIB THREAT INTELLIGENCE ENGINE // EDGE-FIRST // ZERO-BLOAT RAM
        </p>
      </header>

      <section className="grid gap-6 md:grid-cols-3" aria-live="polite">
        <StatBlock
          label="BACKEND /api/health"
          value={backendReachable ? "ONLINE" : "OFFLINE"}
          tone={backendReachable ? "bg-radar text-ink" : "bg-crimson text-canvas"}
        />
        <StatBlock label="WEBSOCKET" value={wsState} tone={wsTone} />
        <StatBlock label="FALLBACK AKTIF" value={health ? String(health.fallback_count) : "—"} tone="bg-canvas text-ink" />
      </section>

      <InterrogationRoom />

      <AnalysisResultPanel />

      <SwarmPanel />

      <VerdictPanel />

      <CommandCenter />

      <TerminalTicker logs={logs} live={wsState === "OPEN"} />

      <section className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="font-display text-3xl font-bold uppercase">INFRASTRUCTURE MATRIX</h2>
          <p className="rounded-none border-4 border-ink bg-ink px-3 py-1 font-mono text-xs font-bold uppercase text-acid">{summary}</p>
        </div>
        {!backendReachable && (
          <p className="rounded-none border-8 border-ink bg-crimson p-4 font-mono text-sm font-bold text-canvas shadow-brutal">
            &gt; BACKEND OFFLINE // cd backend &amp;&amp; .\.venv\Scripts\Activate.ps1 &amp;&amp; uvicorn main:app --reload --host 127.0.0.1 --port 8000
          </p>
        )}
        {health ? (
          <ul className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {health.services.map((svc, i) => (
              <ServiceCard key={svc.key} service={svc} index={i} />
            ))}
          </ul>
        ) : (
          <p className="rounded-none border-8 border-ink bg-concrete p-6 font-mono text-sm font-bold uppercase shadow-brutal">
            MENUNGGU LAPORAN INFRASTRUKTUR...
          </p>
        )}
        <div className="flex flex-wrap gap-6">
          <BrutalButton tone="acid" onClick={() => void refresh()} disabled={scanning}>
            {scanning ? "SCANNING..." : "RE-SCAN INFRA"}
          </BrutalButton>
          <BrutalButton tone="magenta" onClick={ping}>
            PING WEBSOCKET
          </BrutalButton>
          <BrutalButton tone="hazard" disabled={graphBusy || !backendReachable} onClick={() => void loadStress(200)}>
            UJI BEBAN GRAF (200 NODE)
          </BrutalButton>
        </div>
      </section>

      <NoticeStack />
    </main>
  );
}
