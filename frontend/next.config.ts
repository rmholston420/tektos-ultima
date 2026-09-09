import type { NextConfig } from "next";

/**
 * Runtime API proxy target. Frontend components call `/api/*` (same-origin);
 * Next rewrites those to the FastAPI backend so nothing hard-codes the port.
 *
 * WebSocket connections still go directly to the gateway proxy — see
 * `src/lib/env.ts` (NEXT_PUBLIC_TEKTOS_WS_PORT). Only HTTP is rewritten.
 */
const BACKEND_HOST = process.env.TEKTOS_HTTP_HOST || "127.0.0.1";
const BACKEND_PORT = process.env.TEKTOS_HTTP_PORT || "8020";
const BACKEND_ORIGIN = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  experimental: {
    // Nothing yet.
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_ORIGIN}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
