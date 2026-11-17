import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { assetFileNames } from "./scripts/ui-asset-names.mjs";

export default defineConfig({
  base: "./",
  build: {
    outDir: "dist/client",
    assetsInlineLimit: 0,
    manifest: true,
    rollupOptions: { output: { assetFileNames } },
  },
  optimizeDeps: {
    include: ["react", "react-dom/client"],
  },
  server: {
    host: "0.0.0.0",
    watch: { ignored: ['**/.qa/**'] },
    allowedHosts: ["terminal.local"],
    warmup: {
      clientFiles: ["./src/main.jsx"],
    },
  },
  plugins: [react()],
});

