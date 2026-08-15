"use client";

import { useCallback, useRef, useState } from "react";
import { postSSE } from "@/lib/sse";
import { API_BASE } from "@/lib/api";
import type { ChatMessage, Citation, SSEEvent } from "@/lib/types";

export interface StreamState {
  status: string;
  tools: string[];
  citations: Citation[];
  answer: string;
  error: string | null;
  streaming: boolean;
}

const EMPTY: StreamState = {
  status: "",
  tools: [],
  citations: [],
  answer: "",
  error: null,
  streaming: false,
};

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [state, setState] = useState<StreamState>(EMPTY);
  const abortRef = useRef<AbortController | null>(null);
  const sessionRef = useRef<string>(`web-${Date.now().toString(36)}`);

  const send = useCallback(async (text: string) => {
    const history: { role: string; content: string }[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setState({ ...EMPTY, streaming: true, status: "正在理解问题…" });

    const controller = new AbortController();
    abortRef.current = controller;

    const handle = (ev: SSEEvent): void => {
      switch (ev.type) {
        case "status":
          setState((s) => ({ ...s, status: (ev.data.message as string) ?? "" }));
          break;
        case "tool":
          setState((s) => ({ ...s, tools: [...s.tools, (ev.data.name as string) ?? ""] }));
          break;
        case "citation": {
          const cs = (ev.data.citations as Citation[]) ?? [];
          setState((s) => ({ ...s, citations: cs }));
          break;
        }
        case "delta":
          setState((s) => ({ ...s, answer: s.answer + ((ev.data.text as string) ?? "") }));
          break;
        case "done": {
          const answer = (ev.data.answer as string) ?? "";
          const citations = (ev.data.citations as Citation[]) ?? [];
          const sid = (ev.data.session_id as string) ?? "";
          if (sid) sessionRef.current = sid;
          setState({ ...EMPTY, answer, citations });
          setMessages((prev) => [...prev, { role: "assistant", content: answer, citations }]);
          break;
        }
        case "error":
          setState((s) => ({
            ...s,
            error: (ev.data.message as string) ?? "出错了",
            streaming: false,
          }));
          break;
      }
    };

    try {
      await postSSE(`${API_BASE}/api/chat`, {
        session_id: sessionRef.current,
        message: text,
        history,
      }, handle, controller.signal);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setState((s) => ({ ...s, error: "连接失败，请确认后端已启动", streaming: false }));
      }
    } finally {
      setState((s) => (s.streaming ? { ...s, streaming: false } : s));
    }
  }, [messages]);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { messages, state, send, stop };
}
