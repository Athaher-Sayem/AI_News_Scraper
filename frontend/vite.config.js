import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The SPA is served by Django at the site root and consumes the JSON API under
// /api/v1/. In development Vite proxies API calls to the Django server so the
// browser only ever talks to one origin (no CORS needed).
export default defineConfig({
  base: "/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
