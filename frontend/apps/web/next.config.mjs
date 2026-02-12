/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // проксирование /api/* на бэкенд (если запрос приходит на Next, например при API_BASE='')
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:4000';
    const pythonBackend = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    return [
      { source: '/api/:path*', destination: `${api}/api/:path*` },
      // Проксирование тестовых запросов на Python бэкенд
      { source: '/test/:path*', destination: `${pythonBackend}/test/:path*` },
    ];
  },
};

export default nextConfig;
