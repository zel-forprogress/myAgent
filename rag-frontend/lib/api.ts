export type SourceChunk = {
  content: string;
  source?: string | null;
  score?: number | null;
  vector_score?: number | null;
  keyword_score?: number | null;
  rerank_score?: number | null;
  retrieval_type?: "vector" | "keyword" | "hybrid" | string | null;
};

export type UserResponse = {
  id: string;
  username: string;
  role: "admin" | "user";
  created_at: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: UserResponse;
};

export type KnowledgeBaseResponse = {
  id: string;
  name: string;
  slug: string;
  collection_name: string;
  embedding_model?: string | null;
  is_default: boolean;
  created_at: string;
  document_count: number;
};

export type DeleteKnowledgeBaseResponse = {
  success: boolean;
  message: string;
  knowledge_base_id: string;
};

export type ChatResponse = {
  answer: string;
  sources: SourceChunk[];
  route: string;
  task_intent: string;
  task_confidence: number;
  steps: string[];
  retrieval_quality: string;
  rewritten_question: string;
  standalone_question: string;
};

export type RetrievalTestResponse = {
  question: string;
  top_k: number;
  knowledge_base_ids: string[];
  knowledge_base_names: string[];
  collection_names: string[];
  duration_ms: number;
  source_count: number;
  candidate_count: number;
  rerank_enabled: boolean;
  rerank_applied: boolean;
  rerank_model: string;
  rerank_endpoint: string;
  rerank_error: string;
  sources: SourceChunk[];
};

export type RerankSettingsResponse = {
  enabled: boolean;
  model: string;
  endpoint: string;
  source: string;
};

export type RetrievalSettingsResponse = {
  min_score: number;
  default_min_score: number;
  source: string;
};

export type EvaluationCaseResponse = {
  id: string;
  knowledge_base_id: string;
  knowledge_base_name: string;
  question: string;
  expected_sources: string[];
  expected_keywords: string[];
  top_k: number;
  use_rerank: boolean;
  note: string;
  last_status?: string | null;
  last_score?: number | null;
  last_hit?: boolean | null;
  last_ran_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type EvaluationCaseResult = {
  case: EvaluationCaseResponse;
  status: string;
  duration_ms: number;
  source_count: number;
  candidate_count: number;
  max_score: number;
  min_required_score: number;
  quality_passed: boolean;
  source_hit: boolean;
  keyword_hit_rate: number;
  matched_sources: string[];
  matched_keywords: string[];
  rerank_enabled: boolean;
  rerank_applied: boolean;
  rerank_error: string;
  sources: SourceChunk[];
};

export type EvaluationRunResponse = {
  summary: {
    total: number;
    passed: number;
    failed: number;
    source_hit_rate: number;
    quality_pass_rate: number;
    average_score: number;
    average_keyword_hit_rate: number;
    rerank_applied_rate: number;
  };
  results: EvaluationCaseResult[];
};

export type SessionResponse = {
  id: string;
  title: string;
  user_id?: string | null;
  owner_username?: string | null;
  knowledge_base_id?: string | null;
  knowledge_base_name?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type SessionListResponse = {
  sessions: SessionResponse[];
  total?: number;
  page?: number;
  page_size?: number;
};

export type MessageResponse = {
  id: number;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  route: string;
  task_intent: string;
  task_confidence: number;
  retrieval_quality: string;
  rewritten_question: string;
  standalone_question: string;
  source_count: number;
  sources: SourceChunk[];
  steps: string[];
  created_at: string;
};

export type SessionMessagesResponse = {
  session: SessionResponse;
  messages: MessageResponse[];
};

export type DeleteSessionResponse = {
  success: boolean;
  message: string;
  session_id: string;
};

export type DocumentInfo = {
  filename: string;
  file_type: string;
  source: string;
  chunks: number;
  status: string;
  character_count: number;
  uploaded_at: string;
  storage_provider: string;
  storage_bucket?: string | null;
  storage_object_key?: string | null;
  content_type?: string | null;
  file_size: number;
};

export type DocumentsResponse = {
  knowledge_base_id: string;
  knowledge_base_name: string;
  collection: string;
  documents: DocumentInfo[];
  total?: number;
  page?: number;
  page_size?: number;
};

export type IngestResponse = {
  success: boolean;
  message: string;
  chunks: number;
  skipped: number;
  knowledge_base_id: string;
  knowledge_base_name: string;
  collection: string;
  stored_path: string;
  filename: string;
  file_type: string;
  status: string;
  character_count: number;
  uploaded_at: string;
  storage_provider: string;
  storage_bucket?: string | null;
  storage_object_key?: string | null;
  content_type?: string | null;
  file_size: number;
  task_id?: string | null;
};

export type IngestionTaskLogResponse = {
  id: number;
  task_id: string;
  node_name: string;
  status: string;
  message: string;
  details?: Record<string, unknown> | null;
  error?: string | null;
  duration_ms: number;
  started_at: string;
  finished_at?: string | null;
};

export type IngestionTaskStatus =
  | "pending"
  | "queued"
  | "running"
  | "retrying"
  | "success"
  | "failed"
  | "cancelled"
  | "skipped"
  | string;

export type IngestionTaskResponse = {
  id: string;
  knowledge_base_id: string;
  knowledge_base_name: string;
  filename: string;
  source: string;
  task_type: string;
  status: string;
  queue_job_id?: string | null;
  current_node?: string | null;
  message: string;
  chunks: number;
  skipped: number;
  retry_count: number;
  max_retries: number;
  error?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  updated_at: string;
  logs: IngestionTaskLogResponse[];
};

export type IngestionTaskListResponse = {
  tasks: IngestionTaskResponse[];
  total: number;
};

export type DeleteDocumentResponse = {
  success: boolean;
  message: string;
  source: string;
  deleted: number;
  knowledge_base_id: string;
  knowledge_base_name: string;
  collection: string;
};

export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";
