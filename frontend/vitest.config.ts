import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Vitest config — fast unit tests for the recorder + store logic that
 * doesn't need Playwright.  jsdom for the Tiptap editor stub.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: false,
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    // Skip Playwright's e2e/ tree
    exclude: ["e2e/**", "node_modules/**", ".next/**"],
  },
});
