"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { BrutalButton } from "@/components/BrutalButton";
import { NetworkGraph } from "@/components/NetworkGraph";
import { useInterrogationStore } from "@/store/useInterrogationStore";
import type { TaskStatus } from "@/lib/types";

function Stage({ label, done, active }: { label: string; done: boolean; active?: boolean }) {
  return (
    <li
      className={`rounded-none border-4 border-ink px-2 py-1 font-mono text-[11px] font-bold uppercase ${
        done ? "bg-radar" : active ? "bg-acid" : "bg-concrete"
      }`}
    >
      {done ? "■" : "□"} {label}
    </li>
  );
}

const busy = (s: TaskStatus): boolean => s === "working";

export function CommandCenter() {
  const run = useInterrogationStore((s) => s.run);
  const swarmStatus = useInterrogationStore((s) => s.swarm.status);
  const verdict = useInterrogationStore((s) => s.verdict);
  const graph = useInterrogationStore((s) => s.graph);
  const hive = useInterrogationStore((s) => s.hive);
  const dossier = useInterrogationStore((s) => s.dossier);
  const loadGraph = useInterrogationStore((s) => s.loadGraph);
  const loadStress = useInterrogationStore((s) => s.loadStressGraph);
  const syncHiveMind = useInterrogationStore((s) => s.syncHiveMind);
  const exportDossier = useInterrogationStore((s) => s.exportDossier);
  const [consent, setConsent] = useState(false);

  const verdictDone = verdict.status === "done";
  const sessionReady = verdictDone && run.sessionId !== null;

  // Graf sesi dimuat otomatis begitu verdict selesai (data sintetis uji-beban tidak ditimpa).
  useEffect(() => {
    if (sessionReady && graph.status === "idle") void loadGraph();
  }, [sessionReady, graph.status, loadGraph]);

  if (!verdictDone && graph.data === null && graph.status !== "working") return null;

  const buzzers = verdict.data?.cards.filter((c) => c.verdict === "BUZZER").length ?? 0;
  const organics = verdict.data?.cards.filter((c) => c.verdict === "ORGANIC").length ?? 0;

  return (
    <section className="flex flex-col gap-6 rounded-none border-8 border-ink bg-acid p-6 shadow-brutal" aria-label="Command center">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b-8 border-ink pb-4">
        <div>
          <p className="font-mono text-xs font-bold uppercase">PHASE 6 // GRAPH · DOSSIER · HIVE-MIND</p>
          <h2 className="font-display text-4xl font-bold uppercase leading-none">VERDICT COMMAND CENTER</h2>
        </div>
        <motion.div
          initial={{ scale: 2.2, rotate: -8 }}
          animate={{ scale: 1, rotate: -3 }}
          transition={{ type: "spring", stiffness: 650, damping: 22 }}
          className="rounded-none border-8 border-ink bg-ink px-4 py-2 font-display text-2xl font-bold uppercase text-acid shadow-brutal-sm"
        >
          {graph.stress ? "STRESS TEST" : `${buzzers} BUZZER / ${organics} ORGANIK`}
        </motion.div>
      </header>

      {!graph.stress && (
        <ul className="flex flex-wrap gap-2" aria-label="Status pipeline">
          <Stage label="Konteks" done />
          <Stage label="Bukti & OCR" done={run.status === "done"} />
          <Stage label="Swarm" done={swarmStatus === "done"} />
          <Stage label="Verdict" done={verdictDone} />
          <Stage label="Graf" done={graph.status === "done"} active={busy(graph.status)} />
          <Stage label="Hive-Mind" done={hive.status === "done"} active={busy(hive.status)} />
          <Stage label="Dossier" done={dossier.status === "done"} active={busy(dossier.status)} />
        </ul>
      )}

      {graph.status === "working" && (
        <p className="rounded-none border-4 border-ink bg-ink p-3 font-mono text-sm font-bold uppercase text-acid">&gt; MEMBANGUN GRAF & MENGHITUNG SENTRALITAS...</p>
      )}
      {graph.error && <p className="break-words rounded-none border-8 border-ink bg-crimson p-3 font-mono text-sm font-bold text-canvas shadow-brutal">&gt; ERROR GRAF: {graph.error}</p>}

      {graph.data && (
        <>
          <div className="flex flex-wrap items-center gap-3 font-mono text-xs font-bold uppercase">
            <span className={`rounded-none border-4 border-ink px-2 py-1 ${graph.data.mode === "memgraph" ? "bg-radar" : "bg-hazard"}`}>
              MODE GRAF: {graph.data.mode}
              {graph.data.mode === "networkx" ? " (MEMGRAPH TIDAK AKTIF — FALLBACK IN-MEMORY)" : ""}
            </span>
            <span className="rounded-none border-4 border-ink bg-canvas px-2 py-1">{graph.data.stats.algorithm}</span>
          </div>

          {graph.data.patient_zero ? (
            <div className="rounded-none border-8 border-ink bg-hazard p-4 shadow-brutal">
              <p className="font-display text-2xl font-bold uppercase leading-tight">
                PATIENT ZERO (KANDIDAT): {graph.data.patient_zero.name} [{graph.data.patient_zero.node_type}]
              </p>
              <p className="mt-1 font-mono text-xs font-bold">{graph.data.patient_zero.reason}</p>
              {graph.data.patient_zero.boss_account_candidate && (
                <p className="mt-1 font-mono text-xs font-bold uppercase">KANDIDAT AKUN TERPENTING: {graph.data.patient_zero.boss_account_candidate}</p>
              )}
              <p className="mt-2 border-4 border-ink bg-canvas p-2 font-mono text-[11px] font-bold">⚠ {graph.data.patient_zero.caveat}</p>
            </div>
          ) : (
            <p className="rounded-none border-4 border-ink bg-canvas p-3 font-mono text-xs font-bold uppercase">
              TIDAK ADA PUSAT JARINGAN YANG MEMENUHI SYARAT (BUTUH TERHUBUNG KE ≥2 AKUN BUZZER & UNGGUL JELAS) — SISTEM TIDAK MENUDUH SEMBARANG SIMPUL.
            </p>
          )}

          <NetworkGraph map={graph.data} />
        </>
      )}

      {sessionReady && !graph.stress && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="flex flex-col gap-3 rounded-none border-8 border-ink bg-canvas p-4 shadow-brutal">
            <h3 className="font-display text-2xl font-bold uppercase">TAKEDOWN DOSSIER</h3>
            <p className="font-mono text-[11px] font-bold uppercase">
              LAPORAN FORENSIK DIBUAT 100% LOKAL (TANPA PIHAK KETIGA): GROUND TRUTH · TERSANGKA + STEMPEL + EVIDENCE GATE + 6 FITUR · JEJAK SINDIKAT & REVERSE-IMAGE · SNAPSHOT GRAF + PATIENT ZERO · HASH INTEGRITAS.
            </p>
            <div className="flex flex-wrap gap-4">
              <BrutalButton tone="crimson" disabled={busy(dossier.status)} onClick={() => void exportDossier("pdf")}>
                {busy(dossier.status) && dossier.last === "pdf" ? "MEMBUAT PDF..." : "EXPORT PDF"}
              </BrutalButton>
              <BrutalButton tone="canvas" disabled={busy(dossier.status)} onClick={() => void exportDossier("html")}>
                {busy(dossier.status) && dossier.last === "html" ? "MEMBUAT HTML..." : "EXPORT HTML"}
              </BrutalButton>
            </div>
            {dossier.status === "done" && (
              <p className="border-4 border-ink bg-ink p-2 font-mono text-[11px] font-bold uppercase text-radar">
                &gt; {dossier.last?.toUpperCase()} DIUNDUH ({dossier.bytes !== null ? (dossier.bytes / 1024).toFixed(0) : "?"} KB). CETAK / SIMPAN DARI BROWSER JIKA PERLU.
              </p>
            )}
            {dossier.error && <p className="break-words border-4 border-ink bg-crimson p-2 font-mono text-xs font-bold text-canvas">&gt; {dossier.error}</p>}
          </div>

          <div className="flex flex-col gap-3 rounded-none border-8 border-ink bg-canvas p-4 shadow-brutal">
            <h3 className="font-display text-2xl font-bold uppercase">GLOBAL HIVE-MIND</h3>
            <p className="font-mono text-[11px] font-bold uppercase">
              KIRIM HASH USERNAME + SKOR + TIPE + RELASI RINGKAS (&lt; 5 KB/BARIS) KE SUPABASE (FALLBACK SQLITE LOKAL). HASH ADALAH PSEUDONIM, BUKAN ANONIM.
            </p>
            <label className="flex cursor-pointer items-start gap-2 font-mono text-xs font-bold uppercase">
              <input type="checkbox" className="mt-0.5 h-6 w-6 shrink-0 rounded-none border-4 border-ink accent-ink" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              SAYA SETUJU MENGIRIM DATA DI ATAS KE HIVE-MIND
            </label>
            <div>
              <BrutalButton tone="magenta" disabled={!consent || busy(hive.status)} onClick={() => void syncHiveMind(consent)}>
                {busy(hive.status) ? "MENGIRIM..." : "SINKRONKAN"}
              </BrutalButton>
            </div>
            {hive.result && (
              <p className="border-4 border-ink bg-ink p-2 font-mono text-[11px] font-bold uppercase text-radar">
                &gt; {hive.result.synced} BARIS VIA {hive.result.mode.toUpperCase()} · PAYLOAD MAKS {hive.result.max_payload_bytes} B · {hive.result.note}
              </p>
            )}
            {hive.error && <p className="break-words border-4 border-ink bg-crimson p-2 font-mono text-xs font-bold text-canvas">&gt; {hive.error}</p>}
          </div>
        </div>
      )}
    </section>
  );
}
