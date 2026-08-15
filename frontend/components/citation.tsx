"use client";

import Link from "next/link";
import type { Citation } from "@/lib/types";

/** 引用列表：点击跳转到后端原文查看页(高亮对应 chunk)。 */
export function CitationView({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <div className="mt-2 space-y-1 border-t border-slate-200 pt-2">
      <div className="text-[11px] font-semibold text-slate-400">参考来源</div>
      {citations.map((c, i) => (
        <div key={i} className="rounded-md bg-slate-50 p-1.5 text-xs">
          <Link
            href={c.url}
            target="_blank"
            className="font-medium text-blue-600 hover:underline"
          >
            【{c.ref}】{c.doc_name}
          </Link>
          <p className="mt-0.5 line-clamp-2 text-slate-500">{c.snippet}</p>
        </div>
      ))}
    </div>
  );
}
