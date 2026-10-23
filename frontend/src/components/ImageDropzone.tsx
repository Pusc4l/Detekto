"use client";

import { useMemo, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { BrutalButton } from "@/components/BrutalButton";
import { formatBytes, shortHash } from "@/lib/format";
import type { CompressedImage } from "@/lib/types";
import { MAX_IMAGES_PER_BUCKET } from "@/utils/imageCompressor";

interface ImageDropzoneProps {
  inputId: string;
  title: string;
  hint: string;
  images: CompressedImage[];
  pending: number;
  onFiles: (files: File[]) => void;
  onRemove: (id: string) => void;
  onClear: () => void;
}

function Tile({ image, index, onRemove }: { image: CompressedImage; index: number; onRemove: (id: string) => void }) {
  const src = useMemo(() => `data:${image.mime};base64,${image.base64}`, [image.mime, image.base64]);
  const saved = image.originalBytes > 0 ? Math.max(0, Math.round((1 - image.bytes / image.originalBytes) * 100)) : 0;

  return (
    <motion.li
      layout
      initial={{ scale: 1.3, rotate: -3 }}
      animate={{ scale: 1, rotate: 0 }}
      exit={{ scale: 0.6, x: 60 }}
      transition={{ type: "spring", stiffness: 700, damping: 32 }}
      className="flex flex-col rounded-none border-4 border-ink bg-canvas shadow-brutal-sm"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={`Bukti unggahan ${index + 1}`} className="h-28 w-full border-b-4 border-ink bg-concrete object-cover" />
      <div className="flex flex-col gap-1 p-2 font-mono text-[11px] font-bold uppercase leading-tight">
        <span className="truncate" title={image.name}>
          #{String(index + 1).padStart(2, "0")} {image.name}
        </span>
        <span>
          {formatBytes(image.originalBytes)} → {formatBytes(image.bytes)}
        </span>
        <span className="text-ink">
          {image.width}×{image.height} · -{saved}% · SHA {shortHash(image.sha256)}
        </span>
        <BrutalButton size="sm" tone="crimson" className="mt-1" onClick={() => onRemove(image.id)}>
          HAPUS
        </BrutalButton>
      </div>
    </motion.li>
  );
}

export function ImageDropzone({ inputId, title, hint, images, pending, onFiles, onRemove, onClear }: ImageDropzoneProps) {
  const [dragging, setDragging] = useState(false);
  const depth = useRef(0); // penghitung enter/leave agar highlight tidak berkedip pada elemen anak
  const total = images.length + pending;

  const onDragEnter = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    depth.current += 1;
    setDragging(true);
  };
  const onDragLeave = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    depth.current = Math.max(0, depth.current - 1);
    if (depth.current === 0) setDragging(false);
  };
  const onDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    depth.current = 0;
    setDragging(false);
    onFiles(Array.from(e.dataTransfer.files));
  };
  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    onFiles(Array.from(e.target.files ?? []));
    e.target.value = ""; // izinkan memilih file yang sama lagi
  };

  return (
    <section className="flex flex-col gap-4" aria-label={title}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-display text-2xl font-bold uppercase">{title}</h3>
        <span className="rounded-none border-4 border-ink bg-ink px-3 py-1 font-mono text-xs font-bold uppercase text-acid">
          {total}/{MAX_IMAGES_PER_BUCKET} SLOT
        </span>
      </div>

      <div className="flex gap-1" aria-hidden>
        {Array.from({ length: MAX_IMAGES_PER_BUCKET }, (_, i) => {
          const fill =
            i < images.length ? "bg-radar" : i < images.length + pending ? "hazard-stripes animate-stripes" : "bg-canvas";
          return <span key={i} className={`h-4 flex-1 rounded-none border-4 border-ink ${fill}`} />;
        })}
      </div>

      <label
        htmlFor={inputId}
        onDragEnter={onDragEnter}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`flex cursor-pointer flex-col items-center gap-2 rounded-none border-8 border-ink p-6 text-center shadow-brutal focus-within:outline focus-within:outline-4 focus-within:outline-magenta ${
          dragging ? "bg-hazard" : "bg-acid"
        }`}
      >
        <span className="font-display text-3xl font-bold uppercase leading-none">
          {dragging ? "LEPAS SEKARANG!" : "SERET & LEPAS SCREENSHOT"}
        </span>
        <span className="font-mono text-xs font-bold uppercase">{hint}</span>
        <span className="border-4 border-ink bg-canvas px-3 py-1 font-mono text-xs font-bold uppercase">
          ATAU KLIK UNTUK PILIH FILE
        </span>
        <input
          id={inputId}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          className="sr-only"
          onChange={onChange}
        />
      </label>

      {pending > 0 && (
        <p className="rounded-none border-4 border-ink bg-ink px-3 py-2 font-mono text-xs font-bold uppercase text-acid" aria-live="polite">
          &gt; MENGOMPRES {pending} FILE DI RAM BROWSER (CANVAS)...
        </p>
      )}

      {images.length > 0 && (
        <>
          <ul className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
            <AnimatePresence initial={false} mode="popLayout">
              {images.map((img, i) => (
                <Tile key={img.id} image={img} index={i} onRemove={onRemove} />
              ))}
            </AnimatePresence>
          </ul>
          <div>
            <BrutalButton size="sm" tone="canvas" onClick={onClear}>
              KOSONGKAN SEMUA
            </BrutalButton>
          </div>
        </>
      )}
    </section>
  );
}
