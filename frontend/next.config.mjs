/** @type {import('next').NextConfig} */
const isTauriBuild = process.env.TAURI_BUILD === "1";

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Tauri memuat file statis (../out). Mode web biasa (localhost:3000) tetap SSR/dev normal.
  output: isTauriBuild ? "export" : undefined,
  images: { unoptimized: true },
};

export default nextConfig;
