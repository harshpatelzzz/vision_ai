import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// The FastAPI edge node. Override with VITE_API_TARGET when the backend runs elsewhere.
const API_TARGET = process.env.VITE_API_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: true,
    // Dev proxy keeps the browser same-origin so no backend CORS changes are needed in dev.
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
      "/ws": {
        target: API_TARGET,
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
  },
});
