"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { BrutalButton } from "@/components/BrutalButton";
import { useInterrogationStore } from "@/store/useInterrogationStore";
import type { FeedbackResponse, VerdictCard } from "@/lib/types";

const FEATURE_LABEL: Record<string, string> = {
  account_age_risk: "UMUR AKUN (RISIKO)",
  rename_frequency: "FREKUENSI GANTI NAMA",
  engagement_anomaly: "ANOMALI ENGAGEMENT",
  copypaste_similarity: "KEMIRIPAN COPAS",
  gt_deviation: "DEVIASI GROUND TRUTH",
  visual_anomaly: "ANOMALI VISUAL FEED",
};

const TYPE_NAME = { A: "AUTOMATED BOT SCRIPT", B: "PAID HUMAN TROLL", C: "ORGANIC CITIZEN" } as const;

function FeatureBar({ name, value }: { name: string; value: number | null }) {
  const filled = value === null ? 0 : Math.round(Math.max(0, Math.min(1, value)) * 10);
  return (
    <div className="flex flex-col gap-1">
      <p className="font-mono text-[11px] font-bold uppercase">
        {FEATURE_LABEL[name] ?? name}: {value === null ? "TIDAK TERAMATI" : `${(value * 100).toFixed(0)}%`}
      </p>
      <div className="flex gap-0.5" aria-hidden>
        {Array.from({ length: 10 }, (_, i) => (
          <span
            key={i}
            className={`h-3 flex-1 rounded-none border-2 border-ink ${
              value === null ? "bg-concrete" : i < filled ? (value >= 0.6 ? "bg-crimson" : "bg-radar") : "bg-canvas"
            }`}
          />
        ))}
      </div>
    </div>
  );
}

function Stamp({ card }: { card: VerdictCard }) {
  const buzzer = card.verdict === "BUZZER";
  return (
    <motion.div
      initial={{ scale: 2.6, rotate: -14 }}
      animate={{ scale: 1, rotate: -4 }}
      transition={{ type: "spring", stiffness: 700, damping: 20, delay: 0.25 }}
      className={`rounded-none border-8 border-ink px-3 py-2 text-center font-display text-2xl font-bold uppercase leading-tight shadow-brutal-sm ${
        buzzer ? "bg-crimson text-canvas" : "bg-emerald text-ink"
      }`}
    >
      {buzzer ? `${card.score.toFixed(1)}% BUZZER` : "ORGANIC CITIZEN"}
      <span className="block font-mono text-xs">
        TYPE {card.buzzer_type} // {TYPE_NAME[card.buzzer_type]}
      </span>
    </motion.div>
  );
}

function FeedbackResult({ fb }: { fb: FeedbackResponse }) {
  return (
    <p className="rounded-none border-4 border-ink bg-ink p-2 font-mono text-[11px] font-bold uppercase text-radar" aria-live="polite">
      &gt; MODEL v{fb.model_version_before}→v{fb.model_version_after} · partial_fit {fb.update_ms.toFixed(1)} ms · P(BUZZER){" "}
      {fb.raw_score_before.toFixed(3)}%→{fb.raw_score_after.toFixed(3)}% · VONIS KINI {fb.verdict_after}
    </p>
  );
}

function Card({ card, index }: { card: VerdictCard; index: number }) {
  const fb = useInterrogationStore((s) => s.verdict.feedback[card.verdict_id]);
  const sending = useInterrogationStore((s) => s.verdict.sending[card.verdict_id] ?? false);
  const submit = useInterrogationStore((s) => s.submitFeedback);
  const buzzer = card.verdict === "BUZZER";

  return (
    <motion.li
      initial={{ y: -80, rotate: -2 }}
      animate={{ y: 0, rotate: 0, x: [0, -7, 7, -4, 4, 0] }}
      transition={{ type: "spring", stiffness: 520, damping: 26, delay: index * 0.12, x: { delay: index * 0.12 + 0.45, duration: 0.3 } }}
      className={`flex flex-col gap-3 rounded-none border-8 border-ink p-4 shadow-brutal ${buzzer ? "bg-canvas" : "bg-canvas"}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="break-all font-display text-2xl font-bold leading-none">@{card.username}</h4>
          <p className="font-mono text-[11px] font-bold uppercase">
            SKOR FINAL {card.score.toFixed(1)}% · MENTAH {card.raw_score.toFixed(1)}% · AMBANG {card.threshold}% · COVERAGE {(card.coverage * 100).toFixed(0)}%
          </p>
        </div>
        <Stamp card={card} />
      </div>

      <div className={`rounded-none border-4 border-ink p-2 font-mono text-[11px] font-bold uppercase ${card.gate.passed ? "bg-radar" : "bg-acid"}`}>
        EVIDENCE GATE: {card.gate.passed ? "LOLOS" : "MENAHAN"} · SINYAL: {card.gate.elevated.length ? card.gate.elevated.join(", ") : "—"}
        <span className="mt-1 block normal-case">{card.gate.reason}</span>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {Object.entries(card.features).map(([k, v]) => (
          <FeatureBar key={k} name={k} value={v} />
        ))}
      </div>

      {card.nlp && (
        <p className="border-t-4 border-ink pt-2 font-mono text-[11px] font-bold uppercase">
          NLP: AGRESIVITAS {card.nlp.aggression === null ? "—" : `${(card.nlp.aggression * 100).toFixed(0)}%`} · DISTORSI{" "}
          {card.nlp.distortion === null ? "—" : `${(card.nlp.distortion * 100).toFixed(0)}%`} · KEMIRIPAN TERTINGGI {(card.nlp.top_similarity * 100).toFixed(0)}%
          {card.nlp.partners[0] ? ` (DENGAN @${card.nlp.partners[0].username})` : ""}
        </p>
      )}

      <ul className="font-mono text-[11px] font-bold uppercase">
        {card.factors.slice(0, 3).map((f) => (
          <li key={f.feature}>
            ▸ {FEATURE_LABEL[f.feature] ?? f.feature}: kontribusi {f.contribution > 0 ? "+" : ""}
            {f.contribution.toFixed(2)} (bobot {f.weight.toFixed(2)})
          </li>
        ))}
      </ul>
      {card.warnings.map((w, i) => (
        <p key={i} className="border-4 border-ink bg-hazard p-1 font-mono text-[11px] font-bold">⚠ {w}</p>
      ))}

      <div className="flex flex-col gap-3 border-t-4 border-ink pt-3">
        {fb ? (
          <FeedbackResult fb={fb} />
        ) : (
          <div className="flex flex-wrap items-center gap-4">
            <BrutalButton size="sm" tone="radar" disabled={sending} onClick={() => void submit(card.verdict_id, "accurate")}>
              AKURAT
            </BrutalButton>
            <BrutalButton size="sm" tone="crimson" disabled={sending} onClick={() => void submit(card.verdict_id, "missed")}>
              MELESET
            </BrutalButton>
            <span className="font-mono text-[10px] font-bold uppercase">{sending ? "MELATIH MODEL..." : "KOREKSI ANDA MELATIH MODEL SEKETIKA"}</span>
          </div>
        )}
      </div>
    </motion.li>
  );
}

export function VerdictPanel() {
  const swarmStatus = useInterrogationStore((s) => s.swarm.status);
  const verdict = useInterrogationStore((s) => s.verdict);
  const runVerdict = useInterrogationStore((s) => s.runVerdict);
  const refreshModel = useInterrogationStore((s) => s.refreshModel);

  useEffect(() => {
    if (swarmStatus === "done") void refreshModel();
  }, [swarmStatus, refreshModel]);

  if (swarmStatus !== "done") return null;
  const computing = verdict.status === "computing";
  const model = verdict.model;

  return (
    <section className="flex flex-col gap-6 rounded-none border-8 border-ink bg-magenta p-6 shadow-brutal" aria-label="Verdict">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b-8 border-ink pb-4">
        <div>
          <p className="font-mono text-xs font-bold uppercase">PHASE 5 // TRUE LEARNER · STRICT DICTATOR · AMBANG 65%</p>
          <h2 className="font-display text-4xl font-bold uppercase leading-none">THE VERDICT</h2>
        </div>
        <BrutalButton tone="acid" disabled={computing} onClick={() => void runVerdict()}>
          {computing ? "MENGHITUNG..." : verdict.data ? "HITUNG ULANG" : "JATUHKAN VERDICT"}
        </BrutalButton>
      </header>

      {model && (
        <div className="rounded-none border-4 border-ink bg-ink p-3 font-mono text-[11px] font-bold uppercase text-acid">
          MODEL SGD v{model.version} · {model.n_samples} FEEDBACK · SUMBER {model.source} · SIMPAN {model.storage} · BOBOT:{" "}
          {model.weights.map((w) => `${w.name.split("_")[0]} ${w.weight.toFixed(2)}`).join(" | ")}
        </div>
      )}

      <p className="rounded-none border-4 border-ink bg-canvas p-3 font-mono text-[11px] font-bold uppercase">
        VONIS BUZZER HANYA SAH BILA ≥2 KELUARGA SINYAL INDEPENDEN MENYALA & MINIMAL SATU BUKAN TEKS. KEMIRIPAN TEKS SAJA TIDAK CUKUP — ORGANIK SERING MENYALIN SLOGAN.
      </p>

      {verdict.error && (
        <p className="break-words rounded-none border-8 border-ink bg-crimson p-3 font-mono text-sm font-bold text-canvas shadow-brutal">&gt; ERROR: {verdict.error}</p>
      )}

      {verdict.data && (
        <>
          <ul className="grid gap-6 lg:grid-cols-2">
            {verdict.data.cards.map((c, i) => (
              <Card key={c.verdict_id} card={c} index={i} />
            ))}
          </ul>
          <p className="font-mono text-xs font-bold uppercase">
            BUFFER GAMBAR: {verdict.data.media_purged ? "0 BYTE (DIHANCURKAN)" : "MASIH ADA"} · MODEL v{verdict.data.model_version}
          </p>
        </>
      )}
    </section>
  );
}
