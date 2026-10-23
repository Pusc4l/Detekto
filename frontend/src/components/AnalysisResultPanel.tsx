"use client";

import { motion } from "framer-motion";
import { BrutalButton } from "@/components/BrutalButton";
import { useInterrogationStore } from "@/store/useInterrogationStore";
import type { Confidence, GroundTruthContext, RunStatus, TargetEntity } from "@/lib/types";

const MAX_TARGET_CARDS = 6;

const STAMP: Record<Exclude<RunStatus, "idle">, { label: string; tone: string }> = {
  uploading: { label: "UPLOADING", tone: "bg-acid text-ink" },
  analyzing: { label: "ANALYZING", tone: "bg-hazard text-ink" },
  done: { label: "ANALYSIS DONE", tone: "bg-radar text-ink" },
  error: { label: "ANALYSIS FAILED", tone: "bg-crimson text-canvas" },
};

const CONFIDENCE_TONE: Record<Confidence, string> = {
  low: "bg-crimson text-canvas",
  medium: "bg-acid text-ink",
  high: "bg-radar text-ink",
};

const isHttpUrl = (url: string): boolean => /^https?:\/\//i.test(url);

function TargetCard({ target }: { target: TargetEntity }) {
  return (
    <li
      className={`flex flex-col gap-2 rounded-none border-4 border-ink p-3 shadow-brutal-sm ${
        target.injection_flag ? "bg-magenta" : "bg-canvas"
      }`}
    >
      <p className="break-all font-display text-xl font-bold leading-tight">@{target.username}</p>
      <p className="font-mono text-xs font-bold uppercase">
        {target.comment_count} KOMENTAR · {target.total_likes} LIKES · GAMBAR {target.image_indexes.map((i) => i + 1).join(",")}
      </p>
      {target.injection_flag && (
        <p className="rounded-none border-4 border-ink bg-ink px-2 py-1 font-mono text-[11px] font-bold uppercase text-acid">
          ⚠ PERINTAH INJEKSI TERDETEKSI — SINYAL MENCURIGAKAN
        </p>
      )}
      <ul className="flex flex-col gap-1 border-t-4 border-ink pt-2">
        {target.comments.slice(0, 2).map((c, i) => (
          <li key={i} className="break-words font-mono text-xs font-bold">
            &gt; {c.injection_flag ? "[ISI DIREDAKSI: POLA INJEKSI]" : c.text}
            {c.likes > 0 ? ` [${c.likes}♥]` : ""}
          </li>
        ))}
      </ul>
    </li>
  );
}

function GroundTruthBlock({ gt }: { gt: GroundTruthContext }) {
  return (
    <section className="flex flex-col gap-4 rounded-none border-8 border-ink bg-canvas p-4 shadow-brutal">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-display text-2xl font-bold uppercase">GROUND TRUTH</h3>
        <span className={`rounded-none border-4 border-ink px-2 py-1 font-mono text-xs font-bold uppercase ${CONFIDENCE_TONE[gt.confidence]}`}>
          CONFIDENCE {gt.confidence}
        </span>
        <span className="rounded-none border-4 border-ink bg-ink px-2 py-1 font-mono text-xs font-bold uppercase text-acid">
          {gt.reasoning_engine} · {gt.search_engine}
        </span>
      </div>

      {!gt.evidence_grounded && (
        <p className="rounded-none border-4 border-ink bg-hazard p-2 font-mono text-xs font-bold uppercase">
          TIDAK ADA SUMBER EKSTERNAL — FAKTA BELUM TERVERIFIKASI
        </p>
      )}
      {gt.injection_flags.length > 0 && (
        <p className="rounded-none border-4 border-ink bg-magenta p-2 font-mono text-xs font-bold uppercase">
          INJEKSI DI KONTEKS DIREDAKSI: {gt.injection_flags.join(", ")}
        </p>
      )}

      <dl className="grid gap-3 font-mono text-sm font-bold md:grid-cols-2">
        <div className="border-4 border-ink bg-white p-3">
          <dt className="text-xs uppercase">KLAIM UTAMA</dt>
          <dd className="mt-1 break-words">{gt.main_claim || "—"}</dd>
        </div>
        <div className="border-4 border-ink bg-white p-3">
          <dt className="text-xs uppercase">BASELINE NETRAL</dt>
          <dd className="mt-1 break-words">{gt.neutral_baseline}</dd>
        </div>
        <div className="border-4 border-ink bg-white p-3 md:col-span-2">
          <dt className="text-xs uppercase">RINGKASAN FAKTA OBJEKTIF</dt>
          <dd className="mt-1 break-words">{gt.objective_summary}</dd>
        </div>
      </dl>

      {gt.dorking_keywords.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Kata kunci dorking">
          {gt.dorking_keywords.map((k) => (
            <li key={k} className="rounded-none border-4 border-ink bg-acid px-2 py-1 font-mono text-xs font-bold uppercase">
              {k}
            </li>
          ))}
        </ul>
      )}

      {gt.sources.length > 0 && (
        <ul className="flex flex-col gap-2">
          {gt.sources.map((src) => (
            <li key={src.url} className="border-4 border-ink bg-white p-2 font-mono text-xs font-bold">
              <span className={`mr-2 border-2 border-ink px-1 ${src.credible ? "bg-radar" : "bg-concrete"}`}>
                {src.credible ? "KREDIBEL" : "UMUM"}
              </span>
              {isHttpUrl(src.url) ? (
                <a href={src.url} target="_blank" rel="noopener noreferrer" className="break-words underline">
                  {src.title}
                </a>
              ) : (
                <span className="break-words">{src.title}</span>
              )}
              <p className="mt-1 break-words font-normal">{src.snippet}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function AnalysisResultPanel() {
  const run = useInterrogationStore((s) => s.run);
  const reset = useInterrogationStore((s) => s.reset);
  if (run.status === "idle") return null;

  const stamp = STAMP[run.status];
  const result = run.result;
  const shown = result?.targets.slice(0, MAX_TARGET_CARDS) ?? [];

  return (
    <section className="flex flex-col gap-6 rounded-none border-8 border-ink bg-concrete p-6 shadow-brutal" aria-label="Hasil analisis">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b-8 border-ink pb-4">
        <div>
          <p className="font-mono text-xs font-bold uppercase">
            PHASE 3 // INGESTION RESULT {run.sessionId ? `// SESI ${run.sessionId.slice(0, 8).toUpperCase()}` : ""}
            {run.vaultBackend ? ` // VAULT ${run.vaultBackend.toUpperCase()}` : ""}
          </p>
          <h2 className="font-display text-4xl font-bold uppercase leading-none">HASIL INTEROGASI</h2>
        </div>
        <motion.div
          key={run.status}
          initial={{ scale: 2.2, rotate: -9 }}
          animate={{ scale: 1, rotate: -3 }}
          transition={{ type: "spring", stiffness: 650, damping: 22 }}
          className={`rounded-none border-8 border-ink px-4 py-2 font-display text-2xl font-bold uppercase shadow-brutal-sm ${stamp.tone}`}
        >
          {stamp.label}
        </motion.div>
      </header>

      {run.error && (
        <p className="break-words rounded-none border-8 border-ink bg-crimson p-4 font-mono text-sm font-bold text-canvas shadow-brutal">
          &gt; ERROR: {run.error}
        </p>
      )}

      {result && result.warnings.length > 0 && (
        <ul className="flex flex-col gap-2">
          {result.warnings.map((w, i) => (
            <li key={i} className="rounded-none border-4 border-ink bg-hazard p-2 font-mono text-xs font-bold uppercase">
              ⚠ {w}
            </li>
          ))}
        </ul>
      )}

      {result && result.status !== "queued" && (
        <p className="font-mono text-xs font-bold uppercase">
          OCR: {result.ocr_engine ?? "—"} · {result.context_image_count} KONTEKS + {result.evidence_image_count} BUKTI ·{" "}
          {result.targets.length} TARGET · BUFFER GAMBAR {result.media_purged ? "SUDAH DIHANCURKAN" : "MASIH DI RAM (TTL 300s)"}
        </p>
      )}

      {shown.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="font-display text-2xl font-bold uppercase">TARGET TERDETEKSI</h3>
          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {shown.map((t) => (
              <TargetCard key={t.username} target={t} />
            ))}
          </ul>
          {result && result.targets.length > shown.length && (
            <p className="font-mono text-xs font-bold uppercase">+ {result.targets.length - shown.length} TARGET LAIN (LIHAT TERMINAL)</p>
          )}
        </div>
      )}

      {result?.ground_truth && <GroundTruthBlock gt={result.ground_truth} />}

      {(run.status === "done" || run.status === "error") && (
        <div>
          <BrutalButton tone="acid" onClick={reset}>
            NEW INTERROGATION
          </BrutalButton>
        </div>
      )}
    </section>
  );
}
