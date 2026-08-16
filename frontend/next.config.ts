/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["highlight.js"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8020/api/:path*",
      },
    ];
  },
};

export default nextConfig;
