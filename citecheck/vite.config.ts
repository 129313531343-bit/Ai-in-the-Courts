import { defineConfig } from "vite";

// Built into the main site's folder, so one `wrangler pages deploy site` publishes both
// releases: https://ai-in-australian-courts.pages.dev/citecheck/ (DECISIONS.md D038).
export default defineConfig({
  base: "/citecheck/",
  build: {
    outDir: "../site/citecheck", emptyOutDir: true, target: "es2022",
    rollupOptions: { input: { main: "index.html", tools: "tools.html" } },
  },
});
