import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: {
      "/personalities": "http://localhost:8000",
      "/sessions": "http://localhost:8000",
      "/chat": "http://localhost:8000",
      "/story": "http://localhost:8000",
      "/data": "http://localhost:8000",
    },
  },
});