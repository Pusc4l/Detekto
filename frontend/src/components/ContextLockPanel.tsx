"use client";

import { BrutalButton } from "@/components/BrutalButton";
import { ImageDropzone } from "@/components/ImageDropzone";
import { MAX_CONTEXT_CHARS } from "@/lib/sanitize";
import { MIN_CONTEXT_LENGTH, canLockContext, useInterrogationStore } from "@/store/useInterrogationStore";

export function ContextLockPanel() {
  const contextText = useInterrogationStore((s) => s.contextText);
  const images = useInterrogationStore((s) => s.contextImages);
  const pending = useInterrogationStore((s) => s.pending.context);
  const setContextText = useInterrogationStore((s) => s.setContextText);
  const addFiles = useInterrogationStore((s) => s.addFiles);
  const removeImage = useInterrogationStore((s) => s.removeImage);
  const clearBucket = useInterrogationStore((s) => s.clearBucket);
  const setStage = useInterrogationStore((s) => s.setStage);
  const ready = useInterrogationStore((s) => canLockContext(s));

  return (
    <div className="flex flex-col gap-8 rounded-none border-8 border-ink bg-canvas p-6 shadow-brutal">
      <header className="border-b-8 border-ink pb-4">
        <p className="font-mono text-xs font-bold uppercase">STAGE 01 // GROUND TRUTH SETUP</p>
        <h2 className="font-display text-4xl font-bold uppercase leading-none md:text-5xl">CONTEXT LOCK</h2>
        <p className="mt-2 font-mono text-xs font-bold uppercase">
          KUNCI FAKTA SEBELUM MENUDUH. KETIK RINGKASAN TOPIK, UNGGAH SCREENSHOT BERITA/POSTINGAN UTAMA, ATAU KEDUANYA.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <label htmlFor="context-text" className="font-display text-2xl font-bold uppercase">
          RINGKASAN KONTEKS
        </label>
        <textarea
          id="context-text"
          value={contextText}
          maxLength={MAX_CONTEXT_CHARS}
          rows={5}
          onChange={(e) => setContextText(e.target.value)}
          placeholder="CONTOH: POSTINGAN AWAL MEMBAHAS KEBIJAKAN A YANG DIKRITIK WARGA KARENA DAMPAK LINGKUNGAN X"
          className="w-full resize-y rounded-none border-8 border-ink bg-white p-3 font-mono text-sm font-bold text-ink placeholder:text-ink focus:bg-acid focus:outline-none"
        />
        <p className="font-mono text-xs font-bold uppercase">
          {contextText.length}/{MAX_CONTEXT_CHARS} KARAKTER · MIN {MIN_CONTEXT_LENGTH} JIKA TANPA GAMBAR
        </p>
      </section>

      <ImageDropzone
        inputId="context-files"
        title="SCREENSHOT KONTEKS"
        hint="MAKS 10 GAMBAR · JPEG/PNG/WEBP · OTOMATIS DIKOMPRES < 2 MB"
        images={images}
        pending={pending}
        onFiles={(files) => void addFiles("context", files)}
        onRemove={(id) => removeImage("context", id)}
        onClear={() => clearBucket("context")}
      />

      <div className="flex flex-wrap items-center justify-between gap-4 border-t-8 border-ink pt-6">
        <p className="font-mono text-xs font-bold uppercase">
          {ready ? "KONTEKS SIAP DIKUNCI" : pending > 0 ? "MENUNGGU KOMPRESI SELESAI..." : "ISI KONTEKS ATAU UNGGAH GAMBAR UNTUK LANJUT"}
        </p>
        <BrutalButton tone="radar" disabled={!ready} onClick={() => setStage(2)}>
          LOCK CONTEXT →
        </BrutalButton>
      </div>
    </div>
  );
}
