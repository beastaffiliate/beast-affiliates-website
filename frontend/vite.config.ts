import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev mirrors production: the SPA calls same-origin paths, and these proxy to
// the local backend — exactly what frontend/vercel.json does in prod. So the
// app never needs CORS and dev routing matches deploy routing.
const backend = "http://localhost:4201";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/portal": backend,
      "/api": backend,
      "/p": backend,
      "/go": backend,
      "/b": backend,
    },
  },
});
