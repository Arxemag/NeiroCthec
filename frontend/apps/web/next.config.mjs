/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Проксирование: /api/* → Nest. /app-api/* обрабатывается Route Handler (app/app-api/[[...path]]/route.ts) с таймаутом 5 мин.
  async rewrites() {
    const apiDestination =
      process.env.API_PROXY_TARGET ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      'http://localhost:4000';
    return [
      { source: '/api/:path*', destination: `${apiDestination.replace(/\/$/, '')}/api/:path*` },
    ];
  },
};

export default nextConfig;

