export type SourceChunk = {
  content: string;
  source?: string | null;
  score?: number | null;
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
  steps: string[];
  retrieval_quality: string;
  rewritten_question: string;
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
  retrieval_quality: string;
  rewritten_question: string;
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
