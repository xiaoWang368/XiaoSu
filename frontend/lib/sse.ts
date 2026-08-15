/**
 * 手写 SSE 消费：EventSource 不支持 POST，用 fetch + ReadableStream 解析 text/event-stream。
 * 不引第三方库。
 */

import type { SSEEvent, SSEEventType } from "./types";

export async function postSSE(
  url: string,
  body: unknown,
  onEvent: (ev: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  function handleFrame(frame: string): void {
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    const raw = dataLines.join("\n");
    try {
      onEvent({ type: eventName as SSEEventType, data: JSON.parse(raw) });
    } catch {
      onEvent({ type: eventName as SSEEventType, data: { raw } });
    }
  }

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      if (frame.trim()) handleFrame(frame);
    }
  }
  if (buf.trim()) handleFrame(buf);
}
