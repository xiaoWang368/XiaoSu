import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Navbar } from "@/components/navbar";

export const metadata: Metadata = {
  title: "小苏 · 管理后台",
  description: "公司内部 AI 助手「小苏」管理后台",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="h-full bg-slate-50 text-slate-800">
        <div className="flex h-full flex-col">
          <Navbar />
          <main className="min-h-0 flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
