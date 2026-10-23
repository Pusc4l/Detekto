"use client";

import { useCallback, useEffect, useRef } from "react";
import { API_BASE, WS_URL } from "@/lib/config";
import { isHealthReport, isLogEvent } from "@/lib/guards";
import { useSystemStore } from "@/store/useSystemStore";

const HEALTH_INTERVAL_MS = 10_000;
const HEALTH_TIMEOUT_MS = 6_000;
const WS_RETRY_BASE_MS = 1_000;
const WS_RETRY_MAX_MS = 15_000;

/** Polling /api/health + koneksi WebSocket dengan exponential backoff. UI tidak pernah crash saat backend mati. */
export function useBackendLink(): { refresh: () => Promise<void>; ping: () => void } {
  const wsRef = useRef<WebSocket | null>(null);
  const wasReachable = useRef<boolean | null>(null);

  const refresh = useCallback(async () => {
    const store = useSystemStore.getState();
    store.setScanning(true);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
    try {
      const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store", signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body: unknown = await res.json();
      if (!isHealthReport(body)) throw new Error("SKEMA RESPON TIDAK VALID");
      store.setHealth(body);
      if (wasReachable.current !== true) store.pushLocalLog("OK", "HEALTH", "BACKEND TERJANGKAU // /api/health 200 OK");
      wasReachable.current = true;
    } catch (err) {
      store.setBackendDown();
      if (wasReachable.current !== false) {
        const reason = err instanceof Error ? err.message : "UNKNOWN";
        store.pushLocalLog("ERROR", "HEALTH", `BACKEND OFFLINE (${reason.slice(0, 80)})`);
      }
      wasReachable.current = false;
    } finally {
      window.clearTimeout(timer);
      store.setScanning(false);
    }
  }, []);

  const ping = useCallback(() => {
    const ws = wsRef.current;
    const store = useSystemStore.getState();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send("ping");
    } else {
      store.pushLocalLog("WARN", "WS", "PING GAGAL // WEBSOCKET BELUM TERSAMBUNG");
    }
  }, []);

  useEffect(() => {
    let disposed = false;
    let retryTimer: number | undefined;
    let attempt = 0;

    const connect = () => {
      if (disposed) return;
      const store = useSystemStore.getState();
      store.setWsState("CONNECTING");
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        attempt = 0;
        useSystemStore.getState().setWsState("OPEN");
      };
      ws.onmessage = (ev: MessageEvent<unknown>) => {
        if (typeof ev.data !== "string") return;
        try {
          const parsed: unknown = JSON.parse(ev.data);
          if (isLogEvent(parsed)) useSystemStore.getState().pushLog(parsed);
        } catch {
          /* pesan rusak diabaikan */
        }
      };
      ws.onclose = () => {
        if (disposed) return;
        useSystemStore.getState().setWsState("CLOSED");
        const delay = Math.min(WS_RETRY_BASE_MS * 2 ** attempt, WS_RETRY_MAX_MS);
        attempt += 1;
        retryTimer = window.setTimeout(connect, delay);
      };
      ws.onerror = () => ws.close();
    };

    void refresh();
    connect();
    const poll = window.setInterval(() => void refresh(), HEALTH_INTERVAL_MS);

    return () => {
      disposed = true;
      window.clearInterval(poll);
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      const ws = wsRef.current;
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [refresh]);

  return { refresh, ping };
}
