/** 后端 API 封装。`/api/*` 走 Next 反代；`/doc/{id}` 查看页走后端直连。 */

import type { ChatLogItem, DocItem, Settings } from "./types";

/** 反代地址：默认相对(Next 把 /api/* 代理到后端 8000)。 */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
/** 后端直连地址(查看页 /doc/{id} 用)。 */
export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

async function _fetch(url: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res;
}

export async function listDocs(): Promise<DocItem[]> {
  return (await _fetch(`${API_BASE}/api/docs`)).json();
}

export async function uploadDoc(file: File): Promise<{ doc_id: string; name: string; status: string }> {
  const fd = new FormData();
  fd.append("file", file);
  return (await _fetch(`${API_BASE}/api/docs`, { method: "POST", body: fd })).json();
}

export async function deleteDoc(id: string): Promise<void> {
  await _fetch(`${API_BASE}/api/docs/${id}`, { method: "DELETE" });
}

export async function listLogs(params: { user_id?: string; keyword?: string; limit?: number } = {}): Promise<ChatLogItem[]> {
  const q = new URLSearchParams();
  if (params.user_id) q.set("user_id", params.user_id);
  if (params.keyword) q.set("keyword", params.keyword);
  q.set("limit", String(params.limit ?? 50));
  return (await _fetch(`${API_BASE}/api/logs?${q.toString()}`)).json();
}

export async function getSettings(): Promise<Settings> {
  return (await _fetch(`${API_BASE}/api/settings`)).json();
}
