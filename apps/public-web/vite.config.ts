import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const port = Number(env.VITE_NEWS_PORT);
  const apiProxyTarget = env.VITE_PUBLIC_API_PROXY_TARGET;

  if (!Number.isInteger(port) || port <= 0 || !apiProxyTarget) {
    throw new Error("VITE_NEWS_PORT and VITE_PUBLIC_API_PROXY_TARGET must be configured");
  }

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port,
      strictPort: true,
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, "")
        }
      }
    },
    preview: {
      port,
      strictPort: true
    }
  };
});
