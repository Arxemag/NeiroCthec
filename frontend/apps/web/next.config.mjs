/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // проксирование /api/* на бэкенд (если запрос приходит на Next, например при API_BASE='')
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:4000';
    return [{ source: '/api/:path*', destination: `${api}/api/:path*` }];
  },
};

export default nextConfig;

