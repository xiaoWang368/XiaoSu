"use client";

import { useCallback, useEffect, useState } from "react";
import { listLogs } from "@/lib/api";
import { Badge } from "@/components/ui";
import type { ChatLogItem } from "@/lib/types";

export default function LogsPage() {
  const [logs, setLogs] = useState<ChatLogItem[]>([]);
  const [msg, setMsg] = useState("");

  const refresh = useCallback(async () => {
    try {
      setLogs(await listLogs({ limit: 50 }));
    } catch (err) {
      setMsg(`加载日志失败: ${(err as Error).message}(请确认后端已启动)`);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">对话日志</h1>
        <button onClick={() => void refresh()} className="rounded-lg border border-slate-300 px-3 py-1 text-sm text-slate-600 hover:bg-slate-100">
          刷新
        </button>
      </div>
      {msg && <p className="mt-2 text-sm text-slate-500">{msg}</p>}

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              <th className="px-4 py-2">用户</th>
              <th>问题</th>
              <th>回答</th>
              <th>工具</th>
              <th>Token</th>
              <th>拒答</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id} className="border-t border-slate-100 align-top">
                <td className="px-4 py-2 text-slate-500">{l.user_id}</td>
                <td className="max-w-[200px] py-2 text-slate-700">
                  <span className="line-clamp-2">{l.question}</span>
                </td>
                <td className="max-w-[260px] py-2 text-slate-600">
                  <span className="line-clamp-3">{l.answer}</span>
                </td>
                <td className="py-2 text-xs text-blue-600">
                  {l.tools_used && l.tools_used.length ? l.tools_used.join("、") : "-"}
                </td>
                <td className="py-2 text-slate-500">{l.tokens?.total_tokens ?? 0}</td>
                <td className="py-2">{l.refused ? <Badge text="拒答" tone="red" /> : "-"}</td>
                <td className="py-2 text-xs text-slate-400">{new Date(l.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  暂无对话日志
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
