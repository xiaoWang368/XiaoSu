import type { ReactNode } from "react";

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      {title && <h3 className="mb-2 text-sm font-semibold text-slate-700">{title}</h3>}
      {children}
    </div>
  );
}

export function Badge({ text, tone = "gray" }: { text: string; tone?: "gray" | "green" | "red" | "blue" }) {
  const tones: Record<string, string> = {
    gray: "bg-slate-100 text-slate-600",
    green: "bg-green-100 text-green-700",
    red: "bg-red-100 text-red-700",
    blue: "bg-blue-100 text-blue-700",
  };
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {text}
    </span>
  );
}
