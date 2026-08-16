/** 与后端 processor.query_processor.service 强类型契约一一对应，不用 any。 */

export type SSEEventType = "status" | "tool" | "citation" | "delta" | "done" | "error";

export interface Citation {
  ref: string;
  doc_name: string;
  snippet: string;
  url: string;
  char_start: number;
  char_end: number;
}

export interface LLMUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatDone {
  answer: string;
  citations: Citation[];
  refused: boolean;
  tools_used: string[];
  usage: LLMUsage;
  session_id: string;
  message_id: string;
}

export interface SSEEvent {
  type: SSEEventType;
  data: Record<string, unknown>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

/* ===== 管理后台接口类型 ===== */

export interface DocItem {
  id: string;
  name: string;
  ext: string;
  size: number;
  sha256: string;
  status: string; // pending | indexing | indexed | failed
  error: string | null;
  chunk_count: number;
  minio_key: string;
  created_at: string;
  updated_at: string;
}

export interface ChatLogItem {
  id: number;
  session_id: string;
  user_id: string;
  platform: string;
  question: string;
  answer: string;
  tools_used: string[] | null;
  citations: unknown[] | null;
  tokens: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null;
  refused: boolean;
  created_at: string;
}

export interface Settings {
  model: string;
  temperature: number;
  embedding_model: string;
  embedding_dim: number;
  im_platform: string;
  dingtalk_configured: boolean;
}
