import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api → the FastAPI backend on :8000, so the frontend
// can call relative URLs (e.g. /api/market/top) with no CORS friction.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
