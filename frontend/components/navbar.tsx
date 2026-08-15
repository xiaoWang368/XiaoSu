import Link from "next/link";

const LINKS = [
  { href: "/", label: "对话" },
  { href: "/docs", label: "文档管理" },
  { href: "/logs", label: "对话日志" },
  { href: "/settings", label: "设置" },
];

export function Navbar() {
  return (
    <nav className="flex items-center gap-6 border-b bg-white px-6 py-3">
      <span className="text-lg font-bold text-blue-700">小苏 · 管理后台</span>
      <div className="flex gap-4 text-sm">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className="text-slate-600 hover:text-blue-700">
            {l.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
