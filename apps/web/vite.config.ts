import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const repoRoot = fileURLToPath(new URL("../..", import.meta.url));

// https://vite.dev/config/
export default defineConfig({
  envDir: repoRoot,
  plugins: [react()],
});
