"use client";

import { useState } from "react";
import { useChat } from "@/hooks/useChat";
import { CitationView } from "@/components/citation";
import type { ChatMessage } from "@/lib/types";

const SUGGESTIONS = [
  "员工每年有几天年假？",
  "报销发票需要什么材料？",
  "新人入职第一天要做哪些事？",
  "现在几点？",
];

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-xl px-3 py-2 text-sm shadow-sm ${
          isUser ? "bg-blue-600 text-white" : "bg-white border border-slate-200 text-slate-800"
        }`}
      >
        <div className="whitespace-pre-wrap">{message.content}</div>
        {message.citations && message.citations.length > 0 && (
          <CitationView citations={message.citations} />
        )}
      </div>
    </div>
  );
}

export function ChatPanel() {
  const { messages, state, send, stop, clear } = useChat();
  const [input, setInput] = useState("");

  const submit = (): void => {
    const text = input.trim();
    if (!text || state.streaming) return;
    setInput("");
    void send(text);
  };

  const streamingAnswer = state.answer || state.status || state.tools.length > 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b bg-white px-4 py-2">
        <span className="text-sm font-semibold text-slate-700">对话</span>
        {messages.length > 0 && (
          <button onClick={clear} className="text-xs text-slate-400 hover:text-red-500">
            清空对话
          </button>
        )}
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && !streamingAnswer && (
          <div className="mx-auto mt-16 max-w-md text-center">
            <h2 className="text-xl font-bold text-slate-700">你好，我是小苏 👋</h2>
            <p className="mt-2 text-sm text-slate-500">
              公司内部 AI 助手。可以问我员工手册、报销、入职相关的问题，也可以问我考勤、订单、时间。
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <Bubble key={i} message={m} />
        ))}

        {streamingAnswer && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
              {state.status && !state.answer && (
                <div className="text-xs text-slate-400">{state.status}</div>
              )}
              {state.tools.length > 0 && (
                <div className="mb-1 text-xs text-blue-600">已调用工具：{state.tools.join("、")}</div>
              )}
              {state.answer && (
                <div className="whitespace-pre-wrap text-slate-800">
                  {state.answer}
                  <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-blue-500 align-middle" />
                </div>
              )}
              {state.citations.length > 0 && <CitationView citations={state.citations} />}
            </div>
          </div>
        )}

        {state.error && <div className="text-sm text-red-600">{state.error}</div>}
      </div>

      <div className="border-t bg-white p-3">
        <div className="mb-2 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              disabled={state.streaming}
              onClick={() => !state.streaming && void send(s)}
              className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:border-blue-400 hover:text-blue-600 disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="问问小苏…"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
          />
          {state.streaming ? (
            <button
              onClick={stop}
              className="rounded-lg bg-slate-500 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600"
            >
              停止
            </button>
          ) : (
            <button
              onClick={submit}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              发送
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
