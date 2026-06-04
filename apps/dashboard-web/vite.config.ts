import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

const apiProxyTarget = process.env.VITE_DASHBOARD_API_PROXY_TARGET;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: apiProxyTarget
      ? {
          "/api": {
            target: apiProxyTarget,
            changeOrigin: true,
            rewrite: (path) => path.replace(/^\/api/, "")
          }
        }
      : undefined
  },
  preview: {
    port: 5173
  }
});
