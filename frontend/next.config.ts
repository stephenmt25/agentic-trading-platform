import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  images: {
    remotePatterns: [
      { protocol: "https", hostname: "lh3.googleusercontent.com" },
      { protocol: "https", hostname: "avatars.githubusercontent.com" },
    ],
  },

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
          {
            key: "Content-Security-Policy",
            value: (() => {
              // REST API calls go through same-origin Vercel rewrite (/api/backend/*).
              // Only WebSocket needs a direct connection to the backend URL.
              const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").trim();
              const wsUrl = apiUrl.replace(/^https/, "wss").replace(/^http/, "ws");
              return [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                "font-src 'self' https://fonts.gstatic.com",
                "img-src 'self' data: blob: https://lh3.googleusercontent.com https://avatars.githubusercontent.com",
                `connect-src 'self' ${apiUrl} ${wsUrl}`,
              ].join("; ");
            })(),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
