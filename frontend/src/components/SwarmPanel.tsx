"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { BrutalButton } from "@/components/BrutalButton";
import { useInterrogationStore } from "@/store/useInterrogationStore";
import type { SwarmUiStatus, TargetDossier, TargetState } from "@/lib/types";

const STATE_TONE: Record<TargetState, string> = {
  queued: "bg-concrete text-ink",
  running: "bg-acid text-ink",
  done: "bg-radar text-ink",
  private: "bg-acid text-ink",
  login_wall: "bg-hazard text-ink",
  not_found: "bg-concrete text-ink",
  blocked: "bg-crimson text-canvas",
  error: "bg-crimson text-canvas",
};

const STAMP: Record<Exclude<SwarmUiStatus, "idle">, { label: string; tone: string }> = {
  launching: { label: "DEPLOYING", tone: "bg-acid text-ink" },
  running: { label: "SWARM ACTIVE", tone: "bg-hazard text-ink" },
  done: { label: "SWARM DONE", tone: "bg-radar text-ink" },
  error: { label: "SWARM FAILED", tone: "bg-crimson text-canvas" },
};

const fmt = (n: number | null): string => (n === null ? "—" : n.toLocaleString("id-ID"));

function ScoreBar({ label, value, hot }: { label: string; value: number | null; hot: boolean }) {
  const filled = value === null ? 0 : Math.round(Math.max(0, Math.min(1, value)) * 10);
  return (
    <div className="flex flex-col gap-1">
      <p className="font-mono text-[11px] font-bold uppercase">
        {label}: {value === null ? "—" : value.toFixed(2)}
      </p>
      <div className="flex gap-0.5" aria-hidden>
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className={`h-3 flex-1 rounded-none border-2 border-ink ${i < filled ? (hot ? "bg-crimson" : "bg-radar") : "bg-canvas"}`} />
        ))}
      </div>
    </div>
  );
}

function DossierCard({ d, index }: { d: TargetDossier; index: number }) {
  const p = d.profile;
  const photo = d.vision?.profile_photo ?? null;
  const feed = d.vision?.feed ?? null;
  const candidates = [...d.candidate_accounts, ...(d.reverse_image?.matches ?? [])];
  return (
    <motion.li
      initial={{ y: -60, rotate: -2 }}
      animate={{ y: 0, rotate: 0 }}
      transition={{ type: "spring", stiffness: 520, damping: 28, delay: index * 0.08 }}
      className="flex flex-col gap-3 rounded-none border-8 border-ink bg-canvas p-4 shadow-brutal"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="break-all font-display text-2xl font-bold leading-none">@{d.username}</h4>
        <span className={`rounded-none border-4 border-ink px-2 py-1 font-mono text-xs font-bold uppercase ${STATE_TONE[d.state]}`}>{d.state.replace("_", " ")}</span>
      </div>
      {d.state_detail && <p className="border-4 border-ink bg-white p-2 font-mono text-[11px] font-bold uppercase">{d.state_detail}</p>}

      {p && (
        <dl className="grid grid-cols-2 gap-2 font-mono text-xs font-bold uppercase">
          <div className="border-4 border-ink bg-white p-2"><dt>FOLLOWERS</dt><dd className="text-lg">{fmt(p.follower_count)}</dd></div>
          <div className="border-4 border-ink bg-white p-2"><dt>FOLLOWING</dt><dd className="text-lg">{fmt(p.following_count)}</dd></div>
          <div className="border-4 border-ink bg-white p-2"><dt>RASIO</dt><dd className="text-lg">{p.follower_following_ratio ?? "—"}</dd></div>
          <div className="border-4 border-ink bg-white p-2"><dt>BERGABUNG</dt><dd className="text-sm">{p.account_creation_date ?? "—"}</dd></div>
          <div className="col-span-2 border-4 border-ink bg-white p-2 normal-case">
            <dt className="uppercase">BIO · PARSER {p.extraction_engine} · METRIK {p.available_metrics.length}/5</dt>
            <dd className="mt-1 break-words">{p.bio_text || "—"}</dd>
          </div>
        </dl>
      )}

      <div className="flex flex-col gap-2 border-t-4 border-ink pt-3">
        <h5 className="font-display text-lg font-bold uppercase">SYNDICATE LINKS ({d.syndicate_links.length})</h5>
        {d.syndicate_links.length === 0 ? (
          <p className="font-mono text-xs font-bold uppercase">TIDAK ADA TAUTAN GRUP/SOSMED TERDETEKSI</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {d.syndicate_links.slice(0, 8).map((l) => (
              <li key={l.url} className="border-4 border-ink bg-magenta p-1 font-mono text-[11px] font-bold">
                <span className="mr-2 border-2 border-ink bg-ink px-1 uppercase text-acid">{l.platform} {l.kind}</span>
                <span className="mr-2 uppercase">[{l.source}]</span>
                {/* Sengaja BUKAN tautan klik: URL dari target tak tepercaya, hanya dicatat. */}
                <span className="select-all break-all">{l.url}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {(photo || feed) && (
        <div className="flex flex-col gap-2 border-t-4 border-ink pt-3">
          <h5 className="font-display text-lg font-bold uppercase">VISION (RAM-ONLY)</h5>
          {photo && <ScoreBar label="ANOMALI FFT FOTO PROFIL" value={photo.score} hot={photo.label === "suspicious"} />}
          {feed && <ScoreBar label={`KESERAGAMAN FEED (${feed.method.toUpperCase()}, ${feed.images_analyzed} IMG)`} value={feed.cluster_ratio} hot={feed.flagged} />}
          <p className="font-mono text-[10px] font-bold uppercase">INDIKATOR HEURISTIK, BUKAN BUKTI — BOBOT DIPELAJARI MODEL DI FASE 5</p>
        </div>
      )}

      {d.copy_paste.length > 0 && (
        <div className="border-t-4 border-ink pt-3">
          <h5 className="font-display text-lg font-bold uppercase">COPY-PASTE</h5>
          <ul className="font-mono text-xs font-bold">
            {d.copy_paste.map((h) => (
              <li key={h.other_username} className="break-words">
                @{h.other_username} · {(h.similarity * 100).toFixed(0)}% · {h.basis}
              </li>
            ))}
          </ul>
        </div>
      )}

      {candidates.length > 0 && (
        <div className="border-t-4 border-ink pt-3">
          <h5 className="font-display text-lg font-bold uppercase">KANDIDAT AKUN BOS / DUPLIKAT ({candidates.length})</h5>
          <ul className="font-mono text-[11px] font-bold">
            {candidates.slice(0, 6).map((c) => (
              <li key={c.url} className="break-all">
                {c.platform} · {c.handle} · {c.evidence.replace("_", " ")}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="border-t-4 border-ink pt-2 font-mono text-[11px] font-bold uppercase">
        JEJAK PENCARIAN: {d.cross_posts.length} ({d.cross_posts.filter((h) => h.mentions_target).length} MENYEBUT TARGET)
        {d.reverse_image ? ` · REVERSE-IMAGE: ${d.reverse_image.status}` : ""}
      </p>
      {d.warnings.map((w, i) => (
        <p key={i} className="border-4 border-ink bg-hazard p-1 font-mono text-[11px] font-bold uppercase">⚠ {w}</p>
      ))}
    </motion.li>
  );
}

function downloadText(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function SwarmPanel() {
  const runStatus = useInterrogationStore((s) => s.run.status);
  const targetCount = useInterrogationStore((s) => s.run.result?.targets.length ?? 0);
  const sessionId = useInterrogationStore((s) => s.run.sessionId);
  const swarm = useInterrogationStore((s) => s.swarm);
  const runSwarm = useInterrogationStore((s) => s.runSwarm);
  const [forceReverse, setForceReverse] = useState(false);

  if (runStatus !== "done" || targetCount === 0) return null;
  const busy = swarm.status === "launching" || swarm.status === "running";
  const stamp = swarm.status === "idle" ? null : STAMP[swarm.status];
  const dossiers = swarm.data?.dossiers ?? [];

  return (
    <section className="flex flex-col gap-6 rounded-none border-8 border-ink bg-hazard p-6 shadow-brutal" aria-label="Swarm OSINT">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b-8 border-ink pb-4">
        <div>
          <p className="font-mono text-xs font-bold uppercase">
            PHASE 4 // DISTRIBUTED OSINT {swarm.executor ? `// EXECUTOR ${swarm.executor.toUpperCase()}` : ""}
          </p>
          <h2 className="font-display text-4xl font-bold uppercase leading-none">THE SWARM</h2>
        </div>
        {stamp && (
          <motion.div
            key={swarm.status}
            initial={{ scale: 2.2, rotate: -9 }}
            animate={{ scale: 1, rotate: -3 }}
            transition={{ type: "spring", stiffness: 650, damping: 22 }}
            className={`rounded-none border-8 border-ink px-4 py-2 font-display text-2xl font-bold uppercase shadow-brutal-sm ${stamp.tone}`}
          >
            {stamp.label}
          </motion.div>
        )}
      </header>

      <p className="rounded-none border-4 border-ink bg-ink p-3 font-mono text-xs font-bold uppercase text-acid">
        HANYA PROFIL PUBLIK · LOGIN-WALL/CAPTCHA TIDAK DI-BYPASS · TAUTAN SINDIKAT HANYA DICATAT, TIDAK PERNAH DIBUKA · GAMBAR HANYA DI RAM
      </p>

      <div className="flex flex-wrap items-center gap-6">
        <BrutalButton tone="crimson" disabled={busy || !sessionId} onClick={() => void runSwarm(forceReverse)}>
          {busy ? "SWARM BERJALAN..." : dossiers.length > 0 ? "DEPLOY ULANG" : `DEPLOY SWARM (${Math.min(targetCount, 5)} TARGET)`}
        </BrutalButton>
        <label className="flex cursor-pointer items-center gap-2 font-mono text-xs font-bold uppercase">
          <input type="checkbox" checked={forceReverse} disabled={busy} onChange={(e) => setForceReverse(e.target.checked)} className="h-6 w-6 rounded-none border-4 border-ink accent-ink" />
          PAKSA REVERSE-IMAGE UNTUK SEMUA TARGET
        </label>
      </div>

      {swarm.error && (
        <p className="break-words rounded-none border-8 border-ink bg-crimson p-3 font-mono text-sm font-bold text-canvas shadow-brutal">&gt; ERROR: {swarm.error}</p>
      )}

      {dossiers.length > 0 && (
        <ul className="grid gap-6 lg:grid-cols-2">
          {dossiers.map((d, i) => (
            <DossierCard key={d.username} d={d} index={i} />
          ))}
        </ul>
      )}

      {swarm.graph && (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-none border-8 border-ink bg-canvas p-4 shadow-brutal">
          <p className="font-mono text-xs font-bold uppercase">
            GRAPH BATCH: {swarm.graph.batch.nodes.length} NODE / {swarm.graph.batch.edges.length} EDGE · MODE {swarm.graph.graph_mode.toUpperCase()} · SIAP UNTUK MEMGRAPH
          </p>
          <BrutalButton size="sm" tone="acid" onClick={() => downloadText(`detekto-graph-${(sessionId ?? "x").slice(0, 8)}.cypher`, swarm.graph?.cypher ?? "")}>
            UNDUH .CYPHER
          </BrutalButton>
        </div>
      )}
    </section>
  );
}
