/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone", // small Docker image; copies only what is needed
  async rewrites() {
    // The browser calls /api/* on its own origin; Next proxies to the
    // backend. Keeps the client free of CORS and of an env-specific host.
    const target = process.env.BACKEND_URL ?? "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${target}/api/:path*` }];
  },
};
export default nextConfig;
