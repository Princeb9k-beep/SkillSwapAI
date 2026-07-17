import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Code-splitting is handled per-route via React.lazy in src/App.jsx; Vite emits a
// separate chunk for each lazily-imported page automatically.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: { outDir: "dist", sourcemap: false },
});
