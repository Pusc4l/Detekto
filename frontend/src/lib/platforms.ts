import type { Platform } from "@/lib/types";

export interface PlatformDef {
  id: Platform;
  label: string;
  hosts: readonly string[];
}

export const PLATFORMS: readonly PlatformDef[] = [
  { id: "instagram", label: "INSTAGRAM", hosts: ["instagram.com"] },
  { id: "x", label: "X / TWITTER", hosts: ["x.com", "twitter.com"] },
  { id: "tiktok", label: "TIKTOK", hosts: ["tiktok.com"] },
  { id: "facebook", label: "FACEBOOK", hosts: ["facebook.com", "fb.com", "fb.watch"] },
  { id: "youtube", label: "YOUTUBE", hosts: ["youtube.com", "youtu.be"] },
];

export const isPlatform = (v: string): v is Platform => PLATFORMS.some((p) => p.id === v);
