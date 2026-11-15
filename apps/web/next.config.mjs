/** @type {import('next').NextConfig} */
// One-container deployment: set GIGBID_API_PROXY (e.g. http://127.0.0.1:8000) at build time and the web app
// forwards /api/* to the API, so the browser only ever talks to one address. Unset = two addresses (local dev).
const proxy = process.env.GIGBID_API_PROXY;
const nextConfig = {
  reactStrictMode: true,
  compress: !proxy, // compression would hold back the live step stream when it is proxied
  async rewrites() {
    return proxy ? [{ source: "/api/:path*", destination: `${proxy}/api/:path*` }] : [];
  },
};
export default nextConfig;
