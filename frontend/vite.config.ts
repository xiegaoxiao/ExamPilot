import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const path = id.replaceAll("\\", "/");
          if (path.includes("/node_modules/echarts/")) return "echarts";
          if (path.includes("/node_modules/zrender/")) return "zrender";
        },
      },
    },
  },
  test: { environment: "jsdom", include: ["tests/unit/**/*.test.ts"] },
});
