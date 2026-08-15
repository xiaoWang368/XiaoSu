import type { NextConfig } from "next";

/**
 * 后端默认地址。前端通过 /api/* 相对路径请求，由 Next 反代到后端 8000；
 * 也可用 NEXT_PUBLIC_API_BASE 直接指定后端地址（绕过代理，走 CORS）。
 */
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
