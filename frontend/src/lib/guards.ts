import type {
  AnalysisResult,
  FeedbackResponse,
  GraphResponse,
  GraphMap,
  GroundTruthContext,
  HealthReport,
  HiveSyncResult,
  LogEvent,
  LogLevel,
  ServiceState,
  ModelStatus,
  ServiceStatus,
  SwarmStatus,
  TargetEntity,
  UploadResponse,
  VerdictSet,
} from "@/lib/types";

const LEVELS: readonly LogLevel[] = ["SYS", "INFO", "OK", "WARN", "ERROR"];
const STATES: readonly ServiceState[] = ["primary", "fallback", "down"];

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;

export function isLogEvent(v: unknown): v is LogEvent {
  return (
    isRecord(v) &&
    typeof v.ts === "string" &&
    typeof v.source === "string" &&
    typeof v.message === "string" &&
    typeof v.level === "string" &&
    (LEVELS as readonly string[]).includes(v.level)
  );
}

function isServiceStatus(v: unknown): v is ServiceStatus {
  return (
    isRecord(v) &&
    typeof v.key === "string" &&
    typeof v.label === "string" &&
    typeof v.mode === "string" &&
    typeof v.detail === "string" &&
    typeof v.state === "string" &&
    (STATES as readonly string[]).includes(v.state) &&
    (v.latency_ms === null || typeof v.latency_ms === "number")
  );
}

export function isHealthReport(v: unknown): v is HealthReport {
  return (
    isRecord(v) &&
    (v.status === "ok" || v.status === "degraded") &&
    typeof v.app === "string" &&
    typeof v.version === "string" &&
    typeof v.timestamp === "string" &&
    typeof v.primary_count === "number" &&
    typeof v.fallback_count === "number" &&
    typeof v.down_count === "number" &&
    Array.isArray(v.services) &&
    v.services.every(isServiceStatus)
  );
}

/* ------------------------------ Fase 3 ------------------------------ */
const STATUSES = ["queued", "running", "done", "error"] as const;
const CONFIDENCES = ["low", "medium", "high"] as const;

const isStringArray = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === "string");

export function isUploadResponse(v: unknown): v is UploadResponse {
  return (
    isRecord(v) &&
    typeof v.session_id === "string" &&
    /^[0-9a-f]{32}$/.test(v.session_id) &&
    typeof v.ttl_seconds === "number" &&
    (v.vault_backend === "redis" || v.vault_backend === "memory") &&
    typeof v.accepted_context === "number" &&
    typeof v.accepted_evidence === "number" &&
    typeof v.total_bytes === "number"
  );
}

function isTarget(v: unknown): v is TargetEntity {
  return (
    isRecord(v) &&
    typeof v.username === "string" &&
    typeof v.comment_count === "number" &&
    typeof v.total_likes === "number" &&
    Array.isArray(v.image_indexes) &&
    typeof v.injection_flag === "boolean" &&
    Array.isArray(v.comments) &&
    v.comments.every(
      (c) => isRecord(c) && typeof c.text === "string" && typeof c.likes === "number" && typeof c.injection_flag === "boolean",
    )
  );
}

function isGroundTruth(v: unknown): v is GroundTruthContext {
  return (
    isRecord(v) &&
    typeof v.main_claim === "string" &&
    typeof v.objective_summary === "string" &&
    typeof v.neutral_baseline === "string" &&
    isStringArray(v.dorking_keywords) &&
    typeof v.confidence === "string" &&
    (CONFIDENCES as readonly string[]).includes(v.confidence) &&
    typeof v.evidence_grounded === "boolean" &&
    typeof v.reasoning_engine === "string" &&
    typeof v.search_engine === "string" &&
    isStringArray(v.injection_flags) &&
    Array.isArray(v.sources) &&
    v.sources.every(
      (s) => isRecord(s) && typeof s.title === "string" && typeof s.url === "string" && typeof s.snippet === "string" && typeof s.credible === "boolean",
    )
  );
}

export function isAnalysisResult(v: unknown): v is AnalysisResult {
  return (
    isRecord(v) &&
    typeof v.session_id === "string" &&
    typeof v.status === "string" &&
    (STATUSES as readonly string[]).includes(v.status) &&
    typeof v.started_at === "string" &&
    (v.finished_at === null || typeof v.finished_at === "string") &&
    (v.ocr_engine === null || typeof v.ocr_engine === "string") &&
    typeof v.context_image_count === "number" &&
    typeof v.evidence_image_count === "number" &&
    Array.isArray(v.targets) &&
    v.targets.every(isTarget) &&
    (v.ground_truth === null || isGroundTruth(v.ground_truth)) &&
    isStringArray(v.warnings) &&
    (v.error === null || typeof v.error === "string") &&
    typeof v.media_purged === "boolean"
  );
}

/* ------------------------------ Fase 4 ------------------------------ */
const DOSSIER_STATES = ["queued", "running", "done", "private", "login_wall", "not_found", "blocked", "error"] as const;

export function isSwarmStatus(v: unknown): v is SwarmStatus {
  return (
    isRecord(v) &&
    typeof v.session_id === "string" &&
    typeof v.status === "string" &&
    (STATUSES as readonly string[]).includes(v.status) &&
    (v.executor === "celery" || v.executor === "background-tasks") &&
    isStringArray(v.targets) &&
    typeof v.started_at === "string" &&
    (v.error === null || typeof v.error === "string") &&
    Array.isArray(v.dossiers) &&
    v.dossiers.every(
      (d) =>
        isRecord(d) &&
        typeof d.username === "string" &&
        typeof d.state === "string" &&
        (DOSSIER_STATES as readonly string[]).includes(d.state) &&
        Array.isArray(d.syndicate_links) &&
        Array.isArray(d.cross_posts) &&
        Array.isArray(d.copy_paste) &&
        Array.isArray(d.candidate_accounts) &&
        Array.isArray(d.warnings),
    )
  );
}

export function isGraphResponse(v: unknown): v is GraphResponse {
  return (
    isRecord(v) &&
    typeof v.cypher === "string" &&
    (v.graph_mode === "memgraph" || v.graph_mode === "networkx") &&
    isRecord(v.batch) &&
    Array.isArray(v.batch.nodes) &&
    Array.isArray(v.batch.edges) &&
    isRecord(v.force_graph)
  );
}

/* ------------------------------ Fase 5 ------------------------------ */
export function isVerdictSet(v: unknown): v is VerdictSet {
  return (
    isRecord(v) &&
    typeof v.session_id === "string" &&
    typeof v.threshold === "number" &&
    typeof v.model_version === "number" &&
    typeof v.media_purged === "boolean" &&
    Array.isArray(v.cards) &&
    v.cards.every(
      (c) =>
        isRecord(c) &&
        typeof c.verdict_id === "string" &&
        typeof c.username === "string" &&
        (c.verdict === "BUZZER" || c.verdict === "ORGANIC") &&
        (c.buzzer_type === "A" || c.buzzer_type === "B" || c.buzzer_type === "C") &&
        typeof c.score === "number" &&
        typeof c.raw_score === "number" &&
        isRecord(c.gate) &&
        typeof c.gate.passed === "boolean" &&
        isRecord(c.features) &&
        Array.isArray(c.factors) &&
        Array.isArray(c.warnings),
    )
  );
}

export function isFeedbackResponse(v: unknown): v is FeedbackResponse {
  return (
    isRecord(v) &&
    typeof v.verdict_id === "string" &&
    (v.applied_label === "BUZZER" || v.applied_label === "ORGANIC") &&
    typeof v.model_version_before === "number" &&
    typeof v.model_version_after === "number" &&
    typeof v.raw_score_before === "number" &&
    typeof v.raw_score_after === "number" &&
    typeof v.score_after === "number" &&
    (v.verdict_after === "BUZZER" || v.verdict_after === "ORGANIC") &&
    typeof v.update_ms === "number" &&
    typeof v.n_samples === "number"
  );
}

export function isModelStatus(v: unknown): v is ModelStatus {
  return (
    isRecord(v) &&
    typeof v.version === "number" &&
    typeof v.n_samples === "number" &&
    typeof v.threshold === "number" &&
    typeof v.intercept === "number" &&
    typeof v.source === "string" &&
    typeof v.storage === "string" &&
    Array.isArray(v.weights) &&
    v.weights.every((w) => isRecord(w) && typeof w.name === "string" && typeof w.weight === "number")
  );
}

/* ------------------------------ Fase 6 ------------------------------ */
export function isGraphMap(v: unknown): v is GraphMap {
  return (
    isRecord(v) &&
    (v.mode === "memgraph" || v.mode === "networkx") &&
    isRecord(v.stats) &&
    typeof v.stats.nodes === "number" &&
    typeof v.stats.edges === "number" &&
    isRecord(v.paths) &&
    (v.patient_zero === null || (isRecord(v.patient_zero) && typeof v.patient_zero.id === "string" && typeof v.patient_zero.reason === "string")) &&
    Array.isArray(v.nodes) &&
    v.nodes.every(
      (n) =>
        isRecord(n) &&
        typeof n.id === "string" &&
        typeof n.name === "string" &&
        typeof n.kind === "string" &&
        typeof n.centrality === "number" &&
        typeof n.degree === "number" &&
        typeof n.is_patient_zero === "boolean",
    ) &&
    Array.isArray(v.links) &&
    v.links.every((l) => isRecord(l) && typeof l.source === "string" && typeof l.target === "string" && typeof l.type === "string")
  );
}

export function isHiveSyncResult(v: unknown): v is HiveSyncResult {
  return (
    isRecord(v) &&
    (v.mode === "supabase" || v.mode === "sqlite") &&
    typeof v.synced === "number" &&
    typeof v.skipped === "number" &&
    typeof v.max_payload_bytes === "number" &&
    typeof v.note === "string"
  );
}
