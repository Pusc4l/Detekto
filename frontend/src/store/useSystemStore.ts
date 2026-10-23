import { create } from "zustand";
import type { HealthReport, LogEvent, LogLevel, WsState } from "@/lib/types";

const MAX_LOGS = 200;

interface SystemState {
  health: HealthReport | null;
  backendReachable: boolean;
  scanning: boolean;
  wsState: WsState;
  logs: LogEvent[];
  setHealth: (report: HealthReport) => void;
  setBackendDown: () => void;
  setScanning: (value: boolean) => void;
  setWsState: (state: WsState) => void;
  pushLog: (event: LogEvent) => void;
  pushLocalLog: (level: LogLevel, source: string, message: string) => void;
}

export const useSystemStore = create<SystemState>((set) => ({
  health: null,
  backendReachable: false,
  scanning: false,
  wsState: "CONNECTING",
  logs: [],
  setHealth: (report) => set({ health: report, backendReachable: true }),
  setBackendDown: () => set({ backendReachable: false }),
  setScanning: (value) => set({ scanning: value }),
  setWsState: (state) => set({ wsState: state }),
  pushLog: (event) => set((s) => ({ logs: [...s.logs, event].slice(-MAX_LOGS) })),
  pushLocalLog: (level, source, message) =>
    set((s) => ({
      logs: [...s.logs, { ts: new Date().toISOString(), level, source, message }].slice(-MAX_LOGS),
    })),
}));
