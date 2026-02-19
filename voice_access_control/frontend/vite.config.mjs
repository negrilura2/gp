import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0", // Allow external access for Docker
    port: 5173,
    proxy: {
      "/api": {
        // Use environment variable or default to localhost for non-docker environments
        target: process.env.VITE_API_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  }
});

