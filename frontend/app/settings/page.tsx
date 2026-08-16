"use client";

import { useCallback, useEffect, useState } from "react";
import { getSettings } from "@/lib/api";
import { Badge, Card } from "@/components/ui";
import type { Settings } from "@/lib/types";

export default function SettingsPage() {
  const [s, setS] = useState<Settings | null>(null);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      setS(await getSettings());
    } catch (e) {
      setErr(`加载失败: ${(e as Error).message}(请确认后端已启动)`);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-slate-800">设置</h1>
      {err && <p className="mt-2 text-sm text-red-500">{err}</p>}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Card title="模型">
          {s ? (
            <div className="text-sm">
              <div>模型: <b className="text-slate-800">{s.model}</b></div>
              <div className="mt-1 text-slate-500">温度: {s.temperature}</div>
              <div className="mt-1 text-slate-500">嵌入: {s.embedding_model}({s.embedding_dim}维)</div>
            </div>
          ) : (
            <div className="text-sm text-slate-400">加载中…</div>
          )}
        </Card>
        <Card title="IM 接入状态">
          {s ? (
            <div className="flex items-center gap-2 text-sm">
              <Badge text={s.dingtalk_configured ? "已配置" : "未配置"} tone={s.dingtalk_configured ? "green" : "red"} />
              <span className="text-slate-500">钉钉 Stream({s.im_platform})</span>
            </div>
          ) : (
            <div className="text-sm text-slate-400">加载中…</div>
          )}
        </Card>
      </div>
    </div>
  );
}
