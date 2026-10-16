import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the API runs separately; CLEW_API points at it (default http://localhost:8081).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": process.env.CLEW_API ?? "http://localhost:8081" } },
});
