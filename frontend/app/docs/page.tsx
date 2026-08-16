"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteDoc, listDocs, uploadDoc } from "@/lib/api";
import { Badge } from "@/components/ui";
import type { DocItem } from "@/lib/types";

const STATUS_TONE: Record<string, "gray" | "green" | "red" | "blue"> = {
  pending: "gray",
  indexing: "blue",
  indexed: "green",
  failed: "red",
};

export default function DocsPage() {
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const refresh = useCallback(async () => {
    try {
      setDocs(await listDocs());
    } catch (err) {
      setMsg(`加载文档失败: ${(err as Error).message}(请确认后端已启动)`);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setMsg("上传中…");
    try {
      const r = await uploadDoc(file);
      setMsg(`已上传 ${r.name},正在后台索引…`);
      await new Promise((res) => setTimeout(res, 2000));
      await refresh();
    } catch (err) {
      setMsg(`上传失败: ${(err as Error).message}`);
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  };

  const onDelete = async (d: DocItem): Promise<void> => {
    if (!window.confirm(`删除文档「${d.name}」?`)) return;
    try {
      await deleteDoc(d.id);
      setMsg("已删除");
      await refresh();
    } catch (err) {
      setMsg(`删除失败: ${(err as Error).message}`);
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">文档管理</h1>
        <label className="cursor-pointer rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
          {busy ? "上传中…" : "上传文档"}
          <input type="file" className="hidden" accept=".md,.txt,.pdf,.docx" onChange={(e) => void onUpload(e)} />
        </label>
      </div>
      {msg && <p className="mt-2 text-sm text-slate-500">{msg}</p>}

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              <th className="px-4 py-2">名称</th>
              <th>类型</th>
              <th>大小</th>
              <th>状态</th>
              <th>切片</th>
              <th>更新时间</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id} className="border-t border-slate-100">
                <td className="px-4 py-2 font-medium text-slate-800">{d.name}</td>
                <td className="text-slate-500">{d.ext}</td>
                <td className="text-slate-500">{(d.size / 1024).toFixed(1)}KB</td>
                <td>
                  <Badge text={d.status} tone={STATUS_TONE[d.status] ?? "gray"} />
                  {d.error && <span className="ml-1 text-xs text-red-500">{d.error}</span>}
                </td>
                <td className="text-slate-500">{d.chunk_count}</td>
                <td className="text-xs text-slate-400">{new Date(d.created_at).toLocaleString()}</td>
                <td>
                  <button onClick={() => void onDelete(d)} className="text-red-500 hover:underline">
                    删除
                  </button>
                </td>
              </tr>
            ))}
            {docs.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  暂无文档,点击右上角上传
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
