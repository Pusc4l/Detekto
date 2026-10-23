/**
 * DETEKTO :: utils/imageCompressor.ts — Client-Side Ephemeral Image Compressor (Task 2.2)
 *
 * Pipeline 100% di memori browser (Zero-Bloat): File -> validasi magic-bytes -> decode -> Canvas
 * -> JPEG adaptif (< 2MB) -> Base64 + SHA-256. Tidak ada penulisan file ke disk.
 * Re-encode lewat Canvas otomatis membuang metadata EXIF (GPS dsb.) dari screenshot pengguna.
 */
import type { CompressedImage } from "@/lib/types";

export const MAX_IMAGES_PER_BUCKET = 10;
/** Batas keras keluaran: < 2MB desimal (2.000.000 B), lebih ketat daripada 2 MiB. */
export const MAX_OUTPUT_BYTES = 2_000_000;
export const MAX_RAW_BYTES = 25 * 1024 * 1024;

const MAX_LONG_EDGE = 2048;
const MIN_LONG_EDGE = 720;
const MAX_PIXELS = 80_000_000; // anti decompression-bomb
const QUALITY_LADDER: readonly number[] = [0.92, 0.85, 0.76, 0.66, 0.56];
const SCALE_STEP = 0.8;

export type CompressionErrorCode = "EMPTY" | "TOO_LARGE_RAW" | "TYPE" | "DECODE" | "PIXELS" | "UNFIT" | "CANVAS";

export class CompressionError extends Error {
  readonly code: CompressionErrorCode;
  constructor(code: CompressionErrorCode, message: string) {
    super(message);
    this.name = "CompressionError";
    this.code = code;
  }
}

/* ------------------------------ validasi tipe ------------------------------ */
const ascii = (b: Uint8Array, from: number, to: number): string => String.fromCharCode(...Array.from(b.slice(from, to)));

/** Verifikasi tipe lewat magic bytes (bukan ekstensi/MIME klaim klien). SVG & file lain otomatis ditolak. */
async function isSupportedImage(file: File): Promise<boolean> {
  const head = new Uint8Array(await file.slice(0, 12).arrayBuffer());
  const jpeg = head[0] === 0xff && head[1] === 0xd8 && head[2] === 0xff;
  const png = head[0] === 0x89 && ascii(head, 1, 4) === "PNG";
  const webp = ascii(head, 0, 4) === "RIFF" && ascii(head, 8, 12) === "WEBP";
  return jpeg || png || webp;
}

/* --------------------------------- decode --------------------------------- */
interface Decoded {
  source: CanvasImageSource;
  width: number;
  height: number;
  release: () => void;
}

async function decode(file: File): Promise<Decoded> {
  if (typeof createImageBitmap === "function") {
    try {
      const bmp = await createImageBitmap(file);
      return { source: bmp, width: bmp.width, height: bmp.height, release: () => bmp.close() };
    } catch {
      /* lanjut ke fallback HTMLImageElement */
    }
  }
  const url = URL.createObjectURL(file); // blob URL = alamat memori, bukan file disk
  const img = new Image();
  img.decoding = "async";
  img.src = url;
  try {
    await img.decode();
  } catch {
    URL.revokeObjectURL(url);
    throw new CompressionError("DECODE", "GAMBAR RUSAK / TIDAK BISA DIDEKODE");
  }
  return {
    source: img,
    width: img.naturalWidth,
    height: img.naturalHeight,
    release: () => URL.revokeObjectURL(url),
  };
}

/* ------------------------------- canvas surface ------------------------------- */
interface Surface {
  encode: (quality: number) => Promise<Blob>;
  dispose: () => void;
}

/** Gambar sekali ke canvas, lalu encode berkali-kali dengan kualitas berbeda tanpa menggambar ulang. */
function createSurface(source: CanvasImageSource, w: number, h: number): Surface {
  if (typeof OffscreenCanvas !== "undefined") {
    const canvas = new OffscreenCanvas(w, h);
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "#FFFFFF"; // JPEG tidak punya alpha -> hindari latar hitam pada PNG transparan
      ctx.fillRect(0, 0, w, h);
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(source, 0, 0, w, h);
      return {
        encode: (quality) => canvas.convertToBlob({ type: "image/jpeg", quality }),
        dispose: () => {
          canvas.width = 0;
          canvas.height = 0;
        },
      };
    }
  }

  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new CompressionError("CANVAS", "CANVAS 2D TIDAK TERSEDIA");
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(0, 0, w, h);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(source, 0, 0, w, h);
  return {
    encode: (quality) =>
      new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
          (blob) => (blob ? resolve(blob) : reject(new CompressionError("CANVAS", "ENCODE JPEG GAGAL"))),
          "image/jpeg",
          quality,
        );
      }),
    dispose: () => {
      canvas.width = 0; // lepas bitmap backing store (mencegah leak di Safari/WebView)
      canvas.height = 0;
    },
  };
}

/* ---------------------------- base64 & SHA-256 ---------------------------- */
function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") return reject(new CompressionError("CANVAS", "BASE64 GAGAL"));
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : "");
    };
    reader.onerror = () => reject(new CompressionError("CANVAS", "BASE64 GAGAL"));
    reader.readAsDataURL(blob);
  });
}

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

/** SHA-256 murni JS: cadangan bila crypto.subtle tidak ada (konteks non-secure, mis. akses via IP LAN). */
export function sha256Fallback(data: Uint8Array): string {
  const h = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ]);
  const len = data.length;
  const padded = new Uint8Array(((len + 9 + 63) >> 6) << 6);
  padded.set(data);
  padded[len] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padded.length - 8, Math.floor((len * 8) / 0x100000000), false);
  view.setUint32(padded.length - 4, (len * 8) >>> 0, false);

  const w = new Uint32Array(64);
  const rotr = (x: number, n: number): number => (x >>> n) | (x << (32 - n));

  for (let off = 0; off < padded.length; off += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(off + i * 4, false);
    for (let i = 16; i < 64; i++) {
      const w15 = w[i - 15] ?? 0;
      const w2 = w[i - 2] ?? 0;
      const s0 = rotr(w15, 7) ^ rotr(w15, 18) ^ (w15 >>> 3);
      const s1 = rotr(w2, 17) ^ rotr(w2, 19) ^ (w2 >>> 10);
      w[i] = ((w[i - 16] ?? 0) + s0 + (w[i - 7] ?? 0) + s1) >>> 0;
    }
    let a = h[0] ?? 0, b = h[1] ?? 0, c = h[2] ?? 0, d = h[3] ?? 0;
    let e = h[4] ?? 0, f = h[5] ?? 0, g = h[6] ?? 0, hh = h[7] ?? 0;
    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const t1 = (hh + S1 + ch + (K[i] ?? 0) + (w[i] ?? 0)) >>> 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (S0 + maj) >>> 0;
      hh = g; g = f; f = e; e = (d + t1) >>> 0;
      d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    h[0] = ((h[0] ?? 0) + a) >>> 0; h[1] = ((h[1] ?? 0) + b) >>> 0;
    h[2] = ((h[2] ?? 0) + c) >>> 0; h[3] = ((h[3] ?? 0) + d) >>> 0;
    h[4] = ((h[4] ?? 0) + e) >>> 0; h[5] = ((h[5] ?? 0) + f) >>> 0;
    h[6] = ((h[6] ?? 0) + g) >>> 0; h[7] = ((h[7] ?? 0) + hh) >>> 0;
  }
  return Array.from(h, (x) => x.toString(16).padStart(8, "0")).join("");
}

export async function sha256Hex(blob: Blob): Promise<string> {
  const buf = await blob.arrayBuffer();
  const subtle = globalThis.crypto?.subtle;
  if (subtle) {
    const digest = await subtle.digest("SHA-256", buf);
    return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
  }
  return sha256Fallback(new Uint8Array(buf));
}

/* ------------------------------- API publik ------------------------------- */
let idCounter = 0;
const nextId = (): string => `img-${Date.now().toString(36)}-${(idCounter++).toString(36)}`;

export async function compressImage(file: File): Promise<CompressedImage> {
  if (file.size === 0) throw new CompressionError("EMPTY", "FILE KOSONG (0 BYTE)");
  if (file.size > MAX_RAW_BYTES) {
    throw new CompressionError("TOO_LARGE_RAW", `FILE TERLALU BESAR (MAKS ${MAX_RAW_BYTES / (1024 * 1024)} MB MENTAH)`);
  }
  if (!(await isSupportedImage(file))) {
    throw new CompressionError("TYPE", "HANYA JPEG / PNG / WEBP YANG DITERIMA");
  }

  const decoded = await decode(file);
  try {
    const { width, height } = decoded;
    if (width < 1 || height < 1) throw new CompressionError("DECODE", "DIMENSI GAMBAR TIDAK VALID");
    if (width * height > MAX_PIXELS) throw new CompressionError("PIXELS", "RESOLUSI TERLALU TINGGI (> 80 MEGAPIKSEL)");

    let scale = Math.min(1, MAX_LONG_EDGE / Math.max(width, height));
    // Tangga kompresi: turunkan kualitas dulu (jaga ketajaman teks OCR), baru perkecil dimensi.
    for (;;) {
      const tw = Math.max(1, Math.round(width * scale));
      const th = Math.max(1, Math.round(height * scale));
      const surface = createSurface(decoded.source, tw, th);
      try {
        for (const quality of QUALITY_LADDER) {
          const blob = await surface.encode(quality);
          if (blob.size > 0 && blob.size < MAX_OUTPUT_BYTES) {
            const [base64, sha256] = await Promise.all([blobToBase64(blob), sha256Hex(blob)]);
            return {
              id: nextId(),
              name: file.name.slice(0, 80),
              originalBytes: file.size,
              bytes: blob.size,
              width: tw,
              height: th,
              mime: "image/jpeg",
              base64,
              sha256,
            };
          }
        }
      } finally {
        surface.dispose();
      }
      if (Math.max(tw, th) <= MIN_LONG_EDGE) {
        throw new CompressionError("UNFIT", "GAGAL DIKOMPRES DI BAWAH 2 MB TANPA MERUSAK TEKS");
      }
      scale *= SCALE_STEP;
    }
  } finally {
    decoded.release();
  }
}

/** Jalankan tugas dengan batas konkurensi agar 10+ gambar besar tidak menghabiskan RAM / membekukan UI. */
export async function runPool<T>(items: readonly T[], limit: number, worker: (item: T) => Promise<void>): Promise<void> {
  let cursor = 0;
  const lane = async (): Promise<void> => {
    while (cursor < items.length) {
      const item = items[cursor++] as T;
      await worker(item);
      await new Promise<void>((r) => setTimeout(r, 0)); // beri napas ke main thread di antara gambar
    }
  };
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, lane));
}
