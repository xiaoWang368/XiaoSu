"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { postSSE } from "@/lib/sse";
import { BACKEND_URL } from "@/lib/api";
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

/** localStorage 键:持久化会话(session_id + 消息),切页回来不丢。 */
const STORAGE_KEY = "xiaosu_chat_session";

export function useChat() {
  // 初始为空(服务端/客户端一致,避免 SSR hydration 不匹配);
  // localStorage 恢复放到 useEffect(仅客户端执行)。
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [state, setState] = useState<StreamState>(EMPTY);
  const abortRef = useRef<AbortController | null>(null);
  const sessionRef = useRef<string>(`web-${Date.now().toString(36)}`);

  // 客户端挂载后从 localStorage 恢复会话与消息
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const data = JSON.parse(raw) as { sessionId?: string; messages?: ChatMessage[] };
        if (data.sessionId) sessionRef.current = data.sessionId;
        if (data.messages) setMessages(data.messages);
      }
    } catch {
      /* 忽略损坏数据 */
    }
    // 仅挂载时执行一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 持久化:消息一变就存 localStorage,切到其他页面再回来也能恢复
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ sessionId: sessionRef.current, messages }));
    } catch {
      /* 存储失败忽略 */
    }
  }, [messages]);

  const clear = useCallback(() => {
    setMessages([]);
    sessionRef.current = `web-${Date.now().toString(36)}`;
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);

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
          // 答案已提交到 messages,清空流式状态,避免出现两个消息框
          setState(EMPTY);
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
      // 直连后端 8000(Next 反代会缓冲 SSE,导致失去流式效果)
      await postSSE(`${BACKEND_URL}/api/chat`, {
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

  return { messages, state, send, stop, clear };
}
