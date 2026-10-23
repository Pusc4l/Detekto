import { create } from "zustand";
import {
  CompressionError,
  MAX_IMAGES_PER_BUCKET,
  compressImage,
  runPool,
} from "@/utils/imageCompressor";
import { ApiError, computeVerdict, downloadDossier, fetchGraph, fetchGraphMap, fetchModel, fetchStressGraph, fetchResult, fetchSwarm, purgeSession, sendFeedback, startAnalysis, startSwarm, syncHive, uploadEvidence } from "@/lib/api";
import { MAX_CONTEXT_CHARS, sanitizeText, validatePostUrl } from "@/lib/sanitize";
import { useSystemStore } from "@/store/useSystemStore";
import type {
  Bucket,
  DossierKind,
  DossierUiState,
  FeedbackKind,
  GraphUiState,
  HiveUiState,
  CompressedImage,
  InterrogationPayload,
  Notice,
  NoticeTone,
  PayloadImage,
  Platform,
  RunState,
  Stage,
  SwarmRunState,
  VerdictRunState,
} from "@/lib/types";

const COMPRESSION_CONCURRENCY = 2;
const MAX_NOTICES = 5;
const MIN_CONTEXT_CHARS = 10;

const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 180_000;

const SWARM_POLL_INTERVAL_MS = 2000;
const SWARM_POLL_TIMEOUT_MS = 480_000;
const IDLE_GRAPH: GraphUiState = { status: "idle", data: null, error: null, stress: false };
const IDLE_HIVE: HiveUiState = { status: "idle", result: null, error: null };
const IDLE_DOSSIER: DossierUiState = { status: "idle", last: null, error: null, bytes: null };
const IDLE_VERDICT: VerdictRunState = { status: "idle", data: null, error: null, feedback: {}, sending: {}, model: null };
const IDLE_SWARM: SwarmRunState = { status: "idle", executor: null, data: null, graph: null, error: null };

const IDLE_RUN: RunState = { status: "idle", sessionId: null, vaultBackend: null, result: null, error: null };

let noticeSeq = 0;
let swarmToken = 0;
let runToken = 0; // membatalkan polling lama bila pengguna reset / memulai ulang

const sleep = (ms: number): Promise<void> => new Promise((resolve) => window.setTimeout(resolve, ms));

interface InterrogationState {
  stage: Stage;
  contextText: string;
  contextImages: CompressedImage[];
  evidenceImages: CompressedImage[];
  pending: Record<Bucket, number>;
  platform: Platform | "";
  postUrl: string;
  notices: Notice[];
  run: RunState;
  swarm: SwarmRunState;
  verdict: VerdictRunState;
  graph: GraphUiState;
  hive: HiveUiState;
  dossier: DossierUiState;

  setStage: (stage: Stage) => void;
  setContextText: (text: string) => void;
  setPlatform: (platform: Platform | "") => void;
  setPostUrl: (url: string) => void;
  addFiles: (bucket: Bucket, files: FileList | File[]) => Promise<void>;
  removeImage: (bucket: Bucket, id: string) => void;
  clearBucket: (bucket: Bucket) => void;
  notify: (tone: NoticeTone, text: string) => void;
  dismissNotice: (id: number) => void;
  buildPayload: () => InterrogationPayload | null;
  runInterrogation: () => Promise<void>;
  runSwarm: (forceReverseImage: boolean) => Promise<void>;
  runVerdict: () => Promise<void>;
  submitFeedback: (verdictId: string, kind: FeedbackKind) => Promise<void>;
  refreshModel: () => Promise<void>;
  loadGraph: () => Promise<void>;
  loadStressGraph: (nodes: number) => Promise<void>;
  syncHiveMind: (confirm: boolean) => Promise<void>;
  exportDossier: (kind: DossierKind) => Promise<void>;
  reset: () => void;
}

const toPayloadImage = (img: CompressedImage): PayloadImage => ({
  sha256: img.sha256,
  mime: img.mime,
  bytes: img.bytes,
  width: img.width,
  height: img.height,
  base64: img.base64,
});

function describeError(err: unknown, fileName: string): string {
  const name = fileName.slice(0, 28).toUpperCase();
  if (err instanceof CompressionError) return `${name}: ${err.message}`;
  return `${name}: KEGAGALAN TIDAK TERDUGA SAAT KOMPRESI`;
}

const initialState = {
  stage: 1 as Stage,
  contextText: "",
  contextImages: [] as CompressedImage[],
  evidenceImages: [] as CompressedImage[],
  pending: { context: 0, evidence: 0 } as Record<Bucket, number>,
  platform: "" as Platform | "",
  postUrl: "",
  notices: [] as Notice[],
  run: IDLE_RUN,
  swarm: IDLE_SWARM,
  verdict: IDLE_VERDICT,
  graph: IDLE_GRAPH,
  hive: IDLE_HIVE,
  dossier: IDLE_DOSSIER,
};

export const useInterrogationStore = create<InterrogationState>((set, get) => ({
  ...initialState,

  setStage: (stage) => set({ stage }),

  setContextText: (text) => set({ contextText: sanitizeText(text, MAX_CONTEXT_CHARS) }),

  setPlatform: (platform) => set({ platform }),

  setPostUrl: (url) => set({ postUrl: url.slice(0, 400) }),

  notify: (tone, text) =>
    set((s) => ({ notices: [...s.notices, { id: ++noticeSeq, tone, text }].slice(-MAX_NOTICES) })),

  dismissNotice: (id) => set((s) => ({ notices: s.notices.filter((n) => n.id !== id) })),

  addFiles: async (bucket, files) => {
    const list = Array.from(files);
    if (list.length === 0) return;

    const state = get();
    const current = bucket === "context" ? state.contextImages.length : state.evidenceImages.length;
    const free = Math.max(0, MAX_IMAGES_PER_BUCKET - current - state.pending[bucket]);
    const accepted = list.slice(0, free);
    const rejected = list.length - accepted.length;

    if (rejected > 0) {
      get().notify(
        "error",
        `KUOTA ${MAX_IMAGES_PER_BUCKET}/${MAX_IMAGES_PER_BUCKET} PENUH — ${rejected} FILE DITOLAK OTOMATIS`,
      );
    }
    if (accepted.length === 0) return;

    // Reservasi slot SEBELUM kompresi dimulai -> unggahan beruntun tidak bisa menyalip kuota (anti race condition).
    set((s) => ({ pending: { ...s.pending, [bucket]: s.pending[bucket] + accepted.length } }));

    await runPool(accepted, COMPRESSION_CONCURRENCY, async (file) => {
      let image: CompressedImage | null = null;
      let failure: string | null = null;
      try {
        image = await compressImage(file);
      } catch (err) {
        failure = describeError(err, file.name);
      }

      let duplicate = false;
      set((s) => {
        const pending = { ...s.pending, [bucket]: Math.max(0, s.pending[bucket] - 1) };
        if (!image) return { pending };
        const list = bucket === "context" ? s.contextImages : s.evidenceImages;
        if (list.some((i) => i.sha256 === image?.sha256)) {
          duplicate = true;
          return { pending };
        }
        const next = [...list, image];
        return bucket === "context" ? { pending, contextImages: next } : { pending, evidenceImages: next };
      });

      if (failure) get().notify("error", failure);
      else if (duplicate) get().notify("warn", `${file.name.slice(0, 28).toUpperCase()}: DUPLIKAT — DITOLAK`);
    });
  },

  removeImage: (bucket, id) =>
    set((s) =>
      bucket === "context"
        ? { contextImages: s.contextImages.filter((i) => i.id !== id) }
        : { evidenceImages: s.evidenceImages.filter((i) => i.id !== id) },
    ),

  clearBucket: (bucket) => set(bucket === "context" ? { contextImages: [] } : { evidenceImages: [] }),

  buildPayload: () => {
    const s = get();
    const url = validatePostUrl(s.postUrl, s.platform);
    if (s.platform === "" || !url.ok || s.evidenceImages.length === 0) return null;
    return {
      context_text: sanitizeText(s.contextText, MAX_CONTEXT_CHARS).trim(),
      context_images: s.contextImages.map(toPayloadImage),
      platform: s.platform,
      post_url: url.value,
      evidence_images: s.evidenceImages.map(toPayloadImage),
    };
  },

  runInterrogation: async () => {
    const current = get().run.status;
    if (current === "uploading" || current === "analyzing") return;

    const payload = get().buildPayload();
    if (!payload) {
      get().notify("error", "PAYLOAD BELUM LENGKAP — PILIH PLATFORM, URL VALID, & UNGGAH MINIMAL 1 BUKTI");
      return;
    }

    const token = ++runToken;
    const sys = useSystemStore.getState();
    const imageCount = payload.context_images.length + payload.evidence_images.length;
    set({ run: { ...IDLE_RUN, status: "uploading" } });
    sys.pushLocalLog("SYS", "UPLOAD", `MENGIRIM ${imageCount} GAMBAR (BASE64) KE VAULT RAM LOKAL...`);

    try {
      const upload = await uploadEvidence(payload);
      if (token !== runToken) return;
      set({ run: { ...IDLE_RUN, status: "analyzing", sessionId: upload.session_id, vaultBackend: upload.vault_backend } });
      sys.pushLocalLog(
        "OK",
        "UPLOAD",
        `SESI ${upload.session_id.slice(0, 8).toUpperCase()} DITERIMA // ${upload.vault_backend.toUpperCase()} // TTL ${upload.ttl_seconds}s`,
      );

      await startAnalysis(upload.session_id);
      const deadline = Date.now() + POLL_TIMEOUT_MS;
      for (;;) {
        await sleep(POLL_INTERVAL_MS);
        if (token !== runToken) return;
        const result = await fetchResult(upload.session_id);
        if (token !== runToken) return;

        if (result.status === "done") {
          // Server sudah menghancurkan buffer gambar; kosongkan juga RAM browser (Zero-Bloat dua sisi).
          set({
            run: { status: "done", sessionId: upload.session_id, vaultBackend: upload.vault_backend, result, error: null },
            contextImages: [],
            evidenceImages: [],
          });
          get().notify("info", `ANALISIS SELESAI: ${result.targets.length} TARGET TERDETEKSI. RAM BROWSER DIKOSONGKAN.`);
          return;
        }
        if (result.status === "error") {
          const message = result.error ?? "ANALISIS GAGAL";
          set({
            run: { status: "error", sessionId: upload.session_id, vaultBackend: upload.vault_backend, result, error: message },
          });
          get().notify("error", message.slice(0, 220));
          return;
        }
        set((s) => ({ run: { ...s.run, result } }));
        if (Date.now() > deadline) throw new ApiError(0, "TIMEOUT", "ANALISIS MELEBIHI BATAS WAKTU 3 MENIT");
      }
    } catch (err) {
      if (token !== runToken) return;
      const message = err instanceof ApiError ? err.message : "KEGAGALAN TAK TERDUGA SAAT MENGIRIM BUKTI";
      set((s) => ({ run: { ...s.run, status: "error", error: message } }));
      get().notify("error", message.slice(0, 220));
      sys.pushLocalLog("ERROR", "UPLOAD", message.slice(0, 160));
    }
  },

  runSwarm: async (forceReverseImage) => {
    const { run, swarm } = get();
    if (run.status !== "done" || !run.sessionId || swarm.status === "launching" || swarm.status === "running") return;
    const sessionId = run.sessionId;
    const token = ++swarmToken;
    const sys = useSystemStore.getState();
    set({ swarm: { ...IDLE_SWARM, status: "launching" } });
    sys.pushLocalLog("SYS", "SWARM", "MENGERAHKAN SWARM KE TARGET TERATAS (MAKS 5)...");
    try {
      const launched = await startSwarm(sessionId, forceReverseImage);
      if (token !== swarmToken) return;
      set({ swarm: { ...IDLE_SWARM, status: "running", executor: launched.executor } });
      const deadline = Date.now() + SWARM_POLL_TIMEOUT_MS;
      for (;;) {
        await sleep(SWARM_POLL_INTERVAL_MS);
        if (token !== swarmToken) return;
        const data = await fetchSwarm(sessionId);
        if (token !== swarmToken) return;
        if (data.status === "done") {
          const graph = await fetchGraph(sessionId).catch(() => null);
          if (token !== swarmToken) return;
          set({ swarm: { status: "done", executor: data.executor, data, graph, error: null } });
          get().notify("info", `SWARM SELESAI: ${data.dossiers.length} DOSSIER${graph ? `, GRAPH ${graph.batch.nodes.length} NODE / ${graph.batch.edges.length} EDGE` : ""}`);
          return;
        }
        if (data.status === "error") {
          const message = data.error ?? "SWARM GAGAL";
          set({ swarm: { status: "error", executor: data.executor, data, graph: null, error: message } });
          get().notify("error", message.slice(0, 220));
          return;
        }
        set({ swarm: { status: "running", executor: data.executor, data, graph: null, error: null } });
        if (Date.now() > deadline) throw new ApiError(0, "TIMEOUT", "SWARM MELEBIHI BATAS WAKTU 8 MENIT");
      }
    } catch (err) {
      if (token !== swarmToken) return;
      const message = err instanceof ApiError ? err.message : "KEGAGALAN TAK TERDUGA SAAT MENGERAHKAN SWARM";
      set((s) => ({ swarm: { ...s.swarm, status: "error", error: message } }));
      get().notify("error", message.slice(0, 220));
    }
  },

  refreshModel: async () => {
    const model = await fetchModel().catch(() => null);
    if (model) set((s) => ({ verdict: { ...s.verdict, model } }));
  },

  runVerdict: async () => {
    const { run, swarm, verdict } = get();
    if (swarm.status !== "done" || !run.sessionId || verdict.status === "computing") return;
    set({ verdict: { ...IDLE_VERDICT, status: "computing", model: verdict.model } });
    const sys = useSystemStore.getState();
    sys.pushLocalLog("SYS", "VERDICT", "MENGHITUNG VERDICT: FITUR → SGD → EVIDENCE GATE → AMBANG 65%...");
    try {
      const data = await computeVerdict(run.sessionId);
      set((s) => ({ verdict: { ...s.verdict, status: "done", data, error: null } }));
      await get().refreshModel();
      get().notify("info", `VERDICT SELESAI: ${data.cards.filter((c) => c.verdict === "BUZZER").length} BUZZER / ${data.cards.filter((c) => c.verdict === "ORGANIC").length} ORGANIK. BUFFER GAMBAR 0 BYTE.`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "KEGAGALAN TAK TERDUGA SAAT MENGHITUNG VERDICT";
      set((s) => ({ verdict: { ...s.verdict, status: "error", error: message } }));
      get().notify("error", message.slice(0, 220));
    }
  },

  submitFeedback: async (verdictId, kind) => {
    const { verdict } = get();
    if (verdict.sending[verdictId] || verdict.feedback[verdictId]) return;
    set((s) => ({ verdict: { ...s.verdict, sending: { ...s.verdict.sending, [verdictId]: true } } }));
    try {
      const res = await sendFeedback(verdictId, kind);
      set((s) => ({
        verdict: { ...s.verdict, feedback: { ...s.verdict.feedback, [verdictId]: res }, sending: { ...s.verdict.sending, [verdictId]: false } },
      }));
      useSystemStore.getState().pushLocalLog("OK", "LEARNER", `partial_fit() ${res.update_ms.toFixed(1)} ms // v${res.model_version_before}→v${res.model_version_after}`);
      await get().refreshModel();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "FEEDBACK GAGAL DIKIRIM";
      set((s) => ({ verdict: { ...s.verdict, sending: { ...s.verdict.sending, [verdictId]: false } } }));
      get().notify("error", message.slice(0, 220));
    }
  },

  loadGraph: async () => {
    const { run, graph } = get();
    if (!run.sessionId || graph.status === "working") return;
    set({ graph: { status: "working", data: null, error: null, stress: false } });
    try {
      const data = await fetchGraphMap(run.sessionId);
      set({ graph: { status: "done", data, error: null, stress: false } });
      useSystemStore.getState().pushLocalLog(
        "OK", "GRAPH",
        `${data.stats.nodes} NODE / ${data.stats.edges} EDGE // MODE ${data.mode.toUpperCase()} // PATIENT ZERO: ${data.patient_zero ? data.patient_zero.name : "TIDAK ADA"}`,
      );
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "GRAF GAGAL DIMUAT";
      set({ graph: { status: "error", data: null, error: message, stress: false } });
      get().notify("error", message.slice(0, 220));
    }
  },

  loadStressGraph: async (nodes) => {
    if (get().graph.status === "working") return;
    set({ graph: { status: "working", data: null, error: null, stress: true } });
    try {
      const data = await fetchStressGraph(nodes);
      set({ graph: { status: "done", data, error: null, stress: true } });
      useSystemStore.getState().pushLocalLog("SYS", "GRAPH", `UJI BEBAN: ${data.stats.nodes} NODE / ${data.stats.edges} EDGE DIMUAT (SINTETIS)`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "UJI BEBAN GRAF GAGAL";
      set({ graph: { status: "error", data: null, error: message, stress: true } });
      get().notify("error", message.slice(0, 220));
    }
  },

  syncHiveMind: async (confirm) => {
    const { run, hive } = get();
    if (!run.sessionId || hive.status === "working") return;
    set({ hive: { status: "working", result: null, error: null } });
    try {
      const result = await syncHive(run.sessionId, confirm);
      set({ hive: { status: "done", result, error: null } });
      get().notify("info", `HIVE-MIND: ${result.synced} BARIS VIA ${result.mode.toUpperCase()} (PAYLOAD MAKS ${result.max_payload_bytes} B)`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "SINKRONISASI HIVE-MIND GAGAL";
      set({ hive: { status: "error", result: null, error: message } });
      get().notify("error", message.slice(0, 220));
    }
  },

  exportDossier: async (kind) => {
    const { run, dossier } = get();
    if (!run.sessionId || dossier.status === "working") return;
    set({ dossier: { status: "working", last: kind, error: null, bytes: null } });
    try {
      const blob = await downloadDossier(run.sessionId, kind);
      const url = URL.createObjectURL(blob); // blob URL = memori browser; file hanya tersimpan bila pengguna menyimpannya
      const a = document.createElement("a");
      a.href = url;
      a.download = `detekto-dossier-${run.sessionId.slice(0, 8)}.${kind}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 2000);
      set({ dossier: { status: "done", last: kind, error: null, bytes: blob.size } });
      useSystemStore.getState().pushLocalLog("OK", "DOSSIER", `${kind.toUpperCase()} DIUNDUH // ${(blob.size / 1024).toFixed(0)} KB // DIBUAT LOKAL`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "EKSPOR DOSSIER GAGAL";
      set({ dossier: { status: "error", last: kind, error: message, bytes: null } });
      get().notify("error", message.slice(0, 220));
    }
  },

  // Membuang referensi semua string Base64 -> GC browser bebas membersihkan RAM. Sesi server ikut dihapus.
  reset: () => {
    const sessionId = get().run.sessionId;
    runToken += 1;
    swarmToken += 1;
    if (sessionId) void purgeSession(sessionId).catch(() => undefined);
    set({ ...initialState, notices: get().notices });
  },
}));

/* ------------------------------- selector murni ------------------------------- */
type Snapshot = Pick<
  InterrogationState,
  "contextText" | "contextImages" | "evidenceImages" | "pending" | "platform" | "postUrl"
>;

export const canLockContext = (s: Snapshot): boolean =>
  s.pending.context === 0 &&
  (s.contextText.trim().length >= MIN_CONTEXT_CHARS || s.contextImages.length > 0);

export const isRunBusy = (s: Pick<InterrogationState, "run">): boolean =>
  s.run.status === "uploading" || s.run.status === "analyzing";

export const canExecute = (s: Snapshot): boolean =>
  s.pending.evidence === 0 &&
  s.pending.context === 0 &&
  s.evidenceImages.length > 0 &&
  s.platform !== "" &&
  validatePostUrl(s.postUrl, s.platform).ok;

export const MIN_CONTEXT_LENGTH = MIN_CONTEXT_CHARS;
