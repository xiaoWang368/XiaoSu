"use client";

import { useEffect } from "react";
import { BACKEND_URL } from "@/lib/api";

/** 文档查看页：跳转到后端自包含查看器(/doc/{id}?chunk={n}，含高亮)。 */
export default function DocViewerPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ chunk?: string }>;
}) {
  useEffect(() => {
    void (async () => {
      const { id } = await params;
      const { chunk } = await searchParams;
      window.location.href = `${BACKEND_URL}/doc/${id}?chunk=${chunk ?? "0"}`;
    })();
  }, [params, searchParams]);

  return <div className="p-8 text-sm text-slate-500">正在跳转原文查看页…</div>;
}
