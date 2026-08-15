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
