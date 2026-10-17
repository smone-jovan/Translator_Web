import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true, // Allow access from local network (mobile)
    // Explicit allowlist: `true` lets any website reach the dev server via DNS rebinding.
    // localhost and IP addresses are already allowed; add other LAN hostnames here.
    allowedHosts: [".local"],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/images": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
    watch: {
      ignored: [
        "**/backend/**",
        "**/app.db*",
        "**/scratch/**",
        "**/*.db*",
        "**/*.py",
        "**/*.txt",
        "**/*.db-wal",
        "**/*.db-shm",
      ],
    },
  },
  optimizeDeps: {
    include: [
      "@mui/material",
      "@mui/icons-material",
      "@emotion/react",
      "@emotion/styled",
    ],
  },
});
