import { PLATFORMS } from "@/lib/platforms";
import type { Platform } from "@/lib/types";

export const MAX_CONTEXT_CHARS = 2000;
export const MAX_URL_CHARS = 300;

// Karakter kontrol kecuali \t (0x09) dan \n (0x0A); termasuk zero-width / bidi override yang sering dipakai menyamarkan payload.
const UNSAFE_CHARS = /[\u0000-\u0008\u000B-\u001F\u007F\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]/g;

export function sanitizeText(raw: string, max: number): string {
  return raw.replace(UNSAFE_CHARS, "").slice(0, max);
}

export type UrlCheck = { ok: true; value: string | null } | { ok: false; error: string };

/** URL postingan bersifat opsional. Jika diisi: wajib https, tanpa kredensial, dan host harus cocok dengan platform terpilih. */
export function validatePostUrl(raw: string, platform: Platform | ""): UrlCheck {
  const input = raw.trim();
  if (input === "") return { ok: true, value: null };
  if (input.length > MAX_URL_CHARS) return { ok: false, error: `URL TERLALU PANJANG (MAKS ${MAX_URL_CHARS})` };
  if (platform === "") return { ok: false, error: "PILIH PLATFORM DULU SEBELUM MENGISI URL" };

  let url: URL;
  try {
    url = new URL(input);
  } catch {
    return { ok: false, error: "FORMAT URL TIDAK VALID" };
  }
  if (url.protocol !== "https:") return { ok: false, error: "HANYA HTTPS YANG DITERIMA" };
  if (url.username !== "" || url.password !== "") return { ok: false, error: "URL DENGAN KREDENSIAL DITOLAK" };

  const def = PLATFORMS.find((p) => p.id === platform);
  const host = url.hostname.toLowerCase();
  const matches = def?.hosts.some((h) => host === h || host.endsWith(`.${h}`)) ?? false;
  if (!matches) return { ok: false, error: `HOST BUKAN MILIK ${def?.label ?? "PLATFORM"}` };

  return { ok: true, value: url.href };
}
