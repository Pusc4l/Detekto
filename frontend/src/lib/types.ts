export type LogLevel = "SYS" | "INFO" | "OK" | "WARN" | "ERROR";
export type ServiceState = "primary" | "fallback" | "down";
export type WsState = "CONNECTING" | "OPEN" | "CLOSED";

export interface LogEvent {
  ts: string;
  level: LogLevel;
  source: string;
  message: string;
}

export interface ServiceStatus {
  key: string;
  label: string;
  state: ServiceState;
  mode: string;
  detail: string;
  latency_ms: number | null;
}

export interface HealthReport {
  status: "ok" | "degraded";
  app: string;
  version: string;
  timestamp: string;
  primary_count: number;
  fallback_count: number;
  down_count: number;
  services: ServiceStatus[];
}

/* ------------------------- Fase 2: Interrogation Room ------------------------- */
export type Platform = "instagram" | "x" | "tiktok" | "facebook" | "youtube";
export type Stage = 1 | 2;
export type Bucket = "context" | "evidence";
export type NoticeTone = "error" | "warn" | "info";

export interface Notice {
  id: number;
  tone: NoticeTone;
  text: string;
}

/** Gambar yang sudah dikompresi (< 2MB) dan hidup HANYA di RAM browser. */
export interface CompressedImage {
  id: string;
  name: string;
  originalBytes: number;
  bytes: number;
  width: number;
  height: number;
  mime: "image/jpeg";
  /** Base64 murni (tanpa prefix data:) */
  base64: string;
  /** SHA-256 hex dari bytes terkompresi (kunci Smart Hashing di Fase 3) */
  sha256: string;
}

export interface PayloadImage {
  sha256: string;
  mime: "image/jpeg";
  bytes: number;
  width: number;
  height: number;
  base64: string;
}

export interface InterrogationPayload {
  context_text: string;
  context_images: PayloadImage[];
  platform: Platform;
  post_url: string | null;
  evidence_images: PayloadImage[];
}

/* ------------------------- Fase 3: Ingestion, OCR & Ground Truth ------------------------- */
export type AnalysisStatus = "queued" | "running" | "done" | "error";
export type Confidence = "low" | "medium" | "high";
export type RunStatus = "idle" | "uploading" | "analyzing" | "done" | "error";

export interface UploadResponse {
  session_id: string;
  ttl_seconds: number;
  vault_backend: "redis" | "memory";
  accepted_context: number;
  accepted_evidence: number;
  total_bytes: number;
}

export interface TargetComment {
  text: string;
  likes: number;
  image_index: number;
  injection_flag: boolean;
}

export interface TargetEntity {
  username: string;
  comment_count: number;
  total_likes: number;
  image_indexes: number[];
  injection_flag: boolean;
  comments: TargetComment[];
}

export interface GroundTruthSource {
  title: string;
  url: string;
  snippet: string;
  engine: "searxng" | "duckduckgo";
  credible: boolean;
}

export interface GroundTruthContext {
  main_claim: string;
  objective_summary: string;
  neutral_baseline: string;
  dorking_keywords: string[];
  sources: GroundTruthSource[];
  confidence: Confidence;
  evidence_grounded: boolean;
  reasoning_engine: string;
  search_engine: string;
  injection_flags: string[];
}

export interface AnalysisResult {
  session_id: string;
  status: AnalysisStatus;
  started_at: string;
  finished_at: string | null;
  ocr_engine: string | null;
  context_image_count: number;
  evidence_image_count: number;
  targets: TargetEntity[];
  ground_truth: GroundTruthContext | null;
  warnings: string[];
  error: string | null;
  media_purged: boolean;
}

export interface RunState {
  status: RunStatus;
  sessionId: string | null;
  vaultBackend: "redis" | "memory" | null;
  result: AnalysisResult | null;
  error: string | null;
}

/* ------------------------- Fase 4: The Swarm ------------------------- */
export type TargetState = "queued" | "running" | "done" | "private" | "login_wall" | "not_found" | "blocked" | "error";
export type SwarmRunStatus = "queued" | "running" | "done" | "error";
export type SwarmUiStatus = "idle" | "launching" | "running" | "done" | "error";

export interface SyndicateLink {
  platform: string;
  kind: string;
  url: string;
  identifier: string;
  source: string;
  evidence: string;
}

export interface ProfileMetadata {
  account_creation_date: string | null;
  username_change_count: number | null;
  account_location: string | null;
  follower_count: number | null;
  following_count: number | null;
  follower_following_ratio: number | null;
  post_count: number | null;
  is_verified: boolean | null;
  bio_text: string;
  available_metrics: string[];
  metric_weights: Record<string, number>;
  extraction_engine: string;
}

export interface FftResult {
  score: number;
  hf_ratio: number;
  peak_z: number;
  face_detected: boolean | null;
  label: "normal" | "suspicious" | "insufficient";
  calibrated: boolean;
}

export interface FeedUniformity {
  images_analyzed: number;
  cluster_ratio: number | null;
  unique_ratio: number | null;
  method: "phash" | "clip" | "none";
  flagged: boolean;
}

export interface VisionReport {
  profile_photo: FftResult | null;
  feed: FeedUniformity | null;
  images_fetched: number;
  images_rejected: number;
  buffers_destroyed: boolean;
}

export interface CrossPostHit {
  title: string;
  url: string;
  snippet: string;
  engine: "searxng" | "duckduckgo";
  mentions_target: boolean;
}

export interface CopyPasteHit {
  other_username: string;
  similarity: number;
  sample: string;
  basis: "screenshot" | "thread";
}

export interface CandidateAccount {
  platform: string;
  handle: string;
  url: string;
  evidence: "handle_match" | "reverse_image";
}

export interface ReverseImageReport {
  status: "skipped" | "done" | "blocked" | "error";
  reason: string;
  matches: CandidateAccount[];
}

export interface TargetDossier {
  username: string;
  platform: Platform;
  state: TargetState;
  state_detail: string;
  profile: ProfileMetadata | null;
  syndicate_links: SyndicateLink[];
  vision: VisionReport | null;
  cross_posts: CrossPostHit[];
  copy_paste: CopyPasteHit[];
  reverse_image: ReverseImageReport | null;
  candidate_accounts: CandidateAccount[];
  warnings: string[];
  started_at: string | null;
  finished_at: string | null;
}

export interface SwarmStatus {
  session_id: string;
  status: SwarmRunStatus;
  executor: "celery" | "background-tasks";
  targets: string[];
  dossiers: TargetDossier[];
  started_at: string;
  finished_at: string | null;
  error: string | null;
  graph_summary: Record<string, number | string> | null;
}

export interface GraphResponse {
  batch: {
    session_id: string;
    generated_at: string;
    nodes: Array<{ label: string; key: string; props: Record<string, string | number | boolean | null> }>;
    edges: Array<{ type: string; from_key: string; to_key: string }>;
  };
  cypher: string;
  force_graph: { nodes: unknown[]; links: unknown[] };
  graph_mode: "memgraph" | "networkx";
}

export interface SwarmRunState {
  status: SwarmUiStatus;
  executor: "celery" | "background-tasks" | null;
  data: SwarmStatus | null;
  graph: GraphResponse | null;
  error: string | null;
}

/* ------------------------- Fase 5: True Learner ------------------------- */
export type VerdictLabel = "BUZZER" | "ORGANIC";
export type BuzzerType = "A" | "B" | "C";
export type FeedbackKind = "accurate" | "missed";

export interface GateReport {
  passed: boolean;
  elevated: string[];
  reason: string;
}

export interface SimilarityPartner {
  username: string;
  similarity: number;
  source: "tfidf" | "thread" | "self";
}

export interface NlpReport {
  comments_scored: number;
  aggression: number | null;
  distortion: number | null;
  top_similarity: number;
  self_repeat: number;
  partners: SimilarityPartner[];
  engines: string[];
}

export interface FactorContribution {
  feature: string;
  value: number;
  weight: number;
  contribution: number;
}

export interface VerdictCard {
  verdict_id: string;
  username: string;
  platform: Platform;
  verdict: VerdictLabel;
  buzzer_type: BuzzerType;
  score: number;
  raw_score: number;
  threshold: number;
  gate: GateReport;
  features: Record<string, number | null>;
  coverage: number;
  nlp: NlpReport | null;
  factors: FactorContribution[];
  warnings: string[];
  model_version: number;
  created_at: string;
}

export interface VerdictSet {
  session_id: string;
  generated_at: string;
  threshold: number;
  model_version: number;
  media_purged: boolean;
  cards: VerdictCard[];
}

export interface FeedbackResponse {
  verdict_id: string;
  applied_label: VerdictLabel;
  model_version_before: number;
  model_version_after: number;
  raw_score_before: number;
  raw_score_after: number;
  score_after: number;
  verdict_after: VerdictLabel;
  update_ms: number;
  n_samples: number;
}

export interface ModelStatus {
  version: number;
  n_samples: number;
  source: "sqlite" | "supabase" | "bootstrap";
  storage: "sqlite" | "supabase+sqlite";
  weights: Array<{ name: string; weight: number }>;
  intercept: number;
  threshold: number;
  updated_at: string | null;
}

export interface VerdictRunState {
  status: "idle" | "computing" | "done" | "error";
  data: VerdictSet | null;
  error: string | null;
  feedback: Record<string, FeedbackResponse>;
  sending: Record<string, boolean>;
  model: ModelStatus | null;
}

/* ------------------------- Fase 6: Graph, Dossier, Hive-Mind ------------------------- */
export type NodeKind = "buzzer_a" | "buzzer_b" | "organic" | "target" | "discovered" | "group" | "post";

export interface GraphMapNode {
  id: string;
  label: "Account" | "Group" | "Post";
  name: string;
  kind: NodeKind;
  platform: string;
  verdict: VerdictLabel | null;
  buzzer_type: BuzzerType | null;
  score: number | null;
  verdict_id: string | null;
  centrality: number;
  pagerank: number;
  degree: number;
  is_patient_zero: boolean;
  distance_to_pz: number | null;
}

export interface GraphMapLink {
  source: string;
  target: string;
  type: string;
  weight: number;
}

export interface PatientZero {
  id: string;
  name: string;
  node_type: "account" | "group";
  centrality: number;
  degree: number;
  connected_buzzers: number;
  reason: string;
  boss_account_candidate: string | null;
  caveat: string;
}

export interface GraphMap {
  session_id: string;
  mode: "memgraph" | "networkx";
  nodes: GraphMapNode[];
  links: GraphMapLink[];
  patient_zero: PatientZero | null;
  paths: Record<string, string[]>;
  stats: { nodes: number; edges: number; buzzers: number; organics: number; groups: number; algorithm: string };
}

export interface HiveSyncResult {
  mode: "supabase" | "sqlite";
  synced: number;
  skipped: number;
  max_payload_bytes: number;
  note: string;
}

export type DossierKind = "pdf" | "html";
export type TaskStatus = "idle" | "working" | "done" | "error";

export interface GraphUiState {
  status: TaskStatus;
  data: GraphMap | null;
  error: string | null;
  stress: boolean;
}

export interface HiveUiState {
  status: TaskStatus;
  result: HiveSyncResult | null;
  error: string | null;
}

export interface DossierUiState {
  status: TaskStatus;
  last: DossierKind | null;
  error: string | null;
  bytes: number | null;
}
