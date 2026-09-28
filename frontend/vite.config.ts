import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ""), ...process.env };
  const webDomain = env.GRAPHREV_WEB_DOMAIN?.trim();

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: env.GRAPHREV_VIEWER_URL ?? "http://127.0.0.1:8002",
          changeOrigin: true,
        },
      },
    },
    preview: {
      port: 4173,
      ...(webDomain ? { allowedHosts: [webDomain] } : {}),
      proxy: {
        "/api": {
          target: env.GRAPHREV_VIEWER_URL ?? "http://127.0.0.1:8002",
          changeOrigin: true,
        },
      },
    },
    worker: {
      format: "es" as const,
    },
  };
});
