"use client";

import { useMemo } from "react";
import { BrutalButton } from "@/components/BrutalButton";
import { ImageDropzone } from "@/components/ImageDropzone";
import { PLATFORMS, isPlatform } from "@/lib/platforms";
import { MAX_URL_CHARS, validatePostUrl } from "@/lib/sanitize";
import { canExecute, isRunBusy, useInterrogationStore } from "@/store/useInterrogationStore";

export function EvidencePanel() {
  const images = useInterrogationStore((s) => s.evidenceImages);
  const pending = useInterrogationStore((s) => s.pending.evidence);
  const platform = useInterrogationStore((s) => s.platform);
  const postUrl = useInterrogationStore((s) => s.postUrl);
  const setPlatform = useInterrogationStore((s) => s.setPlatform);
  const setPostUrl = useInterrogationStore((s) => s.setPostUrl);
  const addFiles = useInterrogationStore((s) => s.addFiles);
  const removeImage = useInterrogationStore((s) => s.removeImage);
  const clearBucket = useInterrogationStore((s) => s.clearBucket);
  const setStage = useInterrogationStore((s) => s.setStage);
  const runInterrogation = useInterrogationStore((s) => s.runInterrogation);
  const runStatus = useInterrogationStore((s) => s.run.status);
  const busy = useInterrogationStore((s) => isRunBusy(s));
  const ready = useInterrogationStore((s) => canExecute(s));

  const urlCheck = useMemo(() => validatePostUrl(postUrl, platform), [postUrl, platform]);

  return (
    <div className="flex flex-col gap-8 rounded-none border-8 border-ink bg-canvas p-6 shadow-brutal">
      <header className="border-b-8 border-ink pb-4">
        <p className="font-mono text-xs font-bold uppercase">STAGE 02 // TARGET LOCKING</p>
        <h2 className="font-display text-4xl font-bold uppercase leading-none md:text-5xl">TARGET EVIDENCE</h2>
        <p className="mt-2 font-mono text-xs font-bold uppercase">
          PILIH PLATFORM, UNGGAH SCREENSHOT KOMENTAR (MULTI-TARGET DIPISAH OTOMATIS OLEH OCR), URL POSTINGAN OPSIONAL.
        </p>
      </header>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="flex flex-col gap-2">
          <label htmlFor="platform" className="font-display text-2xl font-bold uppercase">
            PLATFORM *
          </label>
          <select
            id="platform"
            value={platform}
            onChange={(e) => setPlatform(isPlatform(e.target.value) ? e.target.value : "")}
            className="w-full cursor-pointer rounded-none border-8 border-ink bg-hazard p-3 font-mono text-sm font-bold uppercase text-ink shadow-brutal-sm focus:bg-acid focus:outline-none"
          >
            <option value="">-- PILIH PLATFORM --</option>
            {PLATFORMS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </section>

        <section className="flex flex-col gap-2">
          <label htmlFor="post-url" className="font-display text-2xl font-bold uppercase">
            URL POSTINGAN (OPSIONAL)
          </label>
          <input
            id="post-url"
            type="url"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            value={postUrl}
            maxLength={400}
            onChange={(e) => setPostUrl(e.target.value)}
            aria-invalid={!urlCheck.ok}
            placeholder="HTTPS://WWW.INSTAGRAM.COM/P/..."
            className={`w-full rounded-none border-8 border-ink p-3 font-mono text-sm font-bold text-ink placeholder:text-ink focus:bg-acid focus:outline-none ${
              urlCheck.ok ? "bg-white" : "bg-crimson text-canvas"
            }`}
          />
          <p className="font-mono text-xs font-bold uppercase">
            {urlCheck.ok
              ? postUrl.trim() === ""
                ? `KOSONG = MODE SCREENSHOT-ONLY · MAKS ${MAX_URL_CHARS} KARAKTER`
                : "URL VALID · DEEP-THREAD SCRAPING AKTIF DI FASE 4"
              : `ERROR: ${urlCheck.error}`}
          </p>
        </section>
      </div>

      <ImageDropzone
        inputId="evidence-files"
        title="SCREENSHOT KOMENTAR"
        hint="MAKS 10 GAMBAR · BOLEH MEMUAT BANYAK AKUN SEKALIGUS · OTOMATIS < 2 MB"
        images={images}
        pending={pending}
        onFiles={(files) => void addFiles("evidence", files)}
        onRemove={(id) => removeImage("evidence", id)}
        onClear={() => clearBucket("evidence")}
      />

      <div className="flex flex-wrap items-center justify-between gap-4 border-t-8 border-ink pt-6">
        <BrutalButton tone="canvas" disabled={busy} onClick={() => setStage(1)}>
          ← BACK
        </BrutalButton>
        <BrutalButton tone="crimson" disabled={!ready || busy} onClick={() => void runInterrogation()} className="px-8 py-4 text-2xl">
          {runStatus === "uploading" ? "TRANSMITTING..." : runStatus === "analyzing" ? "ANALYZING..." : "EXECUTE INTERROGATION"}
        </BrutalButton>
      </div>
    </div>
  );
}
