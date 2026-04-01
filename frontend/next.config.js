/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,

  // Proxy API calls through Vercel to avoid CORS and keep backend URL private
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_URL || "https://ai-stock-market-scanner.onrender.com";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
