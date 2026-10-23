import { API_BASE } from "@/lib/config";
import { isAnalysisResult, isFeedbackResponse, isGraphMap, isGraphResponse, isHiveSyncResult, isModelStatus, isSwarmStatus, isUploadResponse, isVerdictSet } from "@/lib/guards";
import type {
  AnalysisResult,
  DossierKind,
  FeedbackKind,
  FeedbackResponse,
  GraphMap,
  GraphResponse,
  HiveSyncResult,
  InterrogationPayload,
  ModelStatus,
  SwarmStatus,
  UploadResponse,
  VerdictSet,
} from "@/lib/types";

const UPLOAD_TIMEOUT_MS = 90_000;
const DEFAULT_TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;

/** Ubah body error FastAPI ({detail:{code,message}} | {detail:[{loc,msg}]}) menjadi ApiError rapi. */
function toApiError(status: number, body: unknown): ApiError {
  if (isRecord(body)) {
    const detail = body.detail;
    if (isRecord(detail) && typeof detail.message === "string") {
      return new ApiError(status, typeof detail.code === "string" ? detail.code : "ERROR", detail.message);
    }
    if (Array.isArray(detail) && isRecord(detail[0])) {
      const first = detail[0];
      const loc = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : "input";
      const msg = typeof first.msg === "string" ? first.msg : "tidak valid";
      return new ApiError(status, "VALIDATION", `INPUT DITOLAK SERVER (${loc.toUpperCase()}): ${msg}`.slice(0, 220));
    }
    if (typeof detail === "string") return new ApiError(status, "ERROR", detail.slice(0, 220));
  }
  return new ApiError(status, "HTTP", `SERVER MENJAWAB HTTP ${status}`);
}

async function request(path: string, init: RequestInit, timeoutMs: number): Promise<unknown> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, cache: "no-store", signal: controller.signal });
  } catch (err) {
    const timedOut = err instanceof DOMException && err.name === "AbortError";
    throw new ApiError(
      0,
      timedOut ? "TIMEOUT" : "NETWORK",
      timedOut ? "BACKEND TIDAK MERESPON (TIMEOUT)" : "BACKEND TIDAK TERJANGKAU — PASTIKAN UVICORN BERJALAN DI PORT 8000",
    );
  } finally {
    window.clearTimeout(timer);
  }

  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) throw toApiError(res.status, body);
  return body;
}

export async function uploadEvidence(payload: InterrogationPayload): Promise<UploadResponse> {
  const body = await request(
    "/api/upload-evidence",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
    UPLOAD_TIMEOUT_MS,
  );
  if (!isUploadResponse(body)) throw new ApiError(502, "SCHEMA", "RESPON UPLOAD TIDAK SESUAI SKEMA");
  return body;
}

export async function startAnalysis(sessionId: string): Promise<void> {
  await request(`/api/interrogate/${sessionId}/analyze`, { method: "POST" }, DEFAULT_TIMEOUT_MS);
}

export async function fetchResult(sessionId: string): Promise<AnalysisResult> {
  const body = await request(`/api/interrogate/${sessionId}/result`, { method: "GET" }, DEFAULT_TIMEOUT_MS);
  if (!isAnalysisResult(body)) throw new ApiError(502, "SCHEMA", "RESPON HASIL TIDAK SESUAI SKEMA");
  return body;
}

export async function purgeSession(sessionId: string): Promise<void> {
  await request(`/api/interrogate/${sessionId}`, { method: "DELETE" }, DEFAULT_TIMEOUT_MS);
}

export async function startSwarm(sessionId: string, forceReverseImage: boolean): Promise<{ executor: "celery" | "background-tasks"; targets: number }> {
  const body = await request(
    `/api/interrogate/${sessionId}/swarm`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_targets: 5, force_reverse_image: forceReverseImage }),
    },
    DEFAULT_TIMEOUT_MS,
  );
  if (
    !isRecord(body) ||
    (body.executor !== "celery" && body.executor !== "background-tasks") ||
    typeof body.targets !== "number"
  ) {
    throw new ApiError(502, "SCHEMA", "RESPON SWARM TIDAK SESUAI SKEMA");
  }
  return { executor: body.executor, targets: body.targets };
}

export async function fetchSwarm(sessionId: string): Promise<SwarmStatus> {
  const body = await request(`/api/interrogate/${sessionId}/swarm`, { method: "GET" }, DEFAULT_TIMEOUT_MS);
  if (!isSwarmStatus(body)) throw new ApiError(502, "SCHEMA", "RESPON STATUS SWARM TIDAK SESUAI SKEMA");
  return body;
}

export async function fetchGraph(sessionId: string): Promise<GraphResponse> {
  const body = await request(`/api/interrogate/${sessionId}/graph`, { method: "GET" }, DEFAULT_TIMEOUT_MS);
  if (!isGraphResponse(body)) throw new ApiError(502, "SCHEMA", "RESPON GRAPH TIDAK SESUAI SKEMA");
  return body;
}

export async function computeVerdict(sessionId: string): Promise<VerdictSet> {
  const body = await request(`/api/interrogate/${sessionId}/verdict`, { method: "POST" }, 60_000);
  if (!isVerdictSet(body)) throw new ApiError(502, "SCHEMA", "RESPON VERDICT TIDAK SESUAI SKEMA");
  return body;
}

export async function sendFeedback(verdictId: string, feedback: FeedbackKind): Promise<FeedbackResponse> {
  const body = await request(
    "/api/interrogate/feedback",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ verdict_id: verdictId, feedback }) },
    DEFAULT_TIMEOUT_MS,
  );
  if (!isFeedbackResponse(body)) throw new ApiError(502, "SCHEMA", "RESPON FEEDBACK TIDAK SESUAI SKEMA");
  return body;
}

export async function fetchModel(): Promise<ModelStatus> {
  const body = await request("/api/model", { method: "GET" }, DEFAULT_TIMEOUT_MS);
  if (!isModelStatus(body)) throw new ApiError(502, "SCHEMA", "RESPON MODEL TIDAK SESUAI SKEMA");
  return body;
}

export async function fetchGraphMap(sessionId: string): Promise<GraphMap> {
  const body = await request(`/api/interrogate/${sessionId}/graphmap`, { method: "GET" }, 30_000);
  if (!isGraphMap(body)) throw new ApiError(502, "SCHEMA", "RESPON GRAF TIDAK SESUAI SKEMA");
  return body;
}

export async function fetchStressGraph(nodes: number, seed = 1): Promise<GraphMap> {
  const body = await request(`/api/graph/stress?nodes=${Math.max(20, Math.min(1000, Math.trunc(nodes)))}&seed=${Math.trunc(seed)}`, { method: "GET" }, 30_000);
  if (!isGraphMap(body)) throw new ApiError(502, "SCHEMA", "RESPON GRAF UJI TIDAK SESUAI SKEMA");
  return body;
}

export async function syncHive(sessionId: string, confirm: boolean): Promise<HiveSyncResult> {
  const body = await request(
    `/api/interrogate/${sessionId}/hive-sync`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm }) },
    30_000,
  );
  if (!isHiveSyncResult(body)) throw new ApiError(502, "SCHEMA", "RESPON HIVE-MIND TIDAK SESUAI SKEMA");
  return body;
}

/** Unduh dossier sebagai Blob di memori (dibuat 100% lokal oleh backend; tidak ada layanan pihak ketiga). */
export async function downloadDossier(sessionId: string, kind: DossierKind): Promise<Blob> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 90_000);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/interrogate/${sessionId}/dossier.${kind}`, { cache: "no-store", signal: controller.signal });
  } catch {
    throw new ApiError(0, "NETWORK", "BACKEND TIDAK TERJANGKAU SAAT MEMBUAT DOSSIER");
  } finally {
    window.clearTimeout(timer);
  }
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    throw toApiError(res.status, body);
  }
  return res.blob();
}
