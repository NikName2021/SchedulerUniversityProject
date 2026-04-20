import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ["localhost", "harmlessly-paned-marketta.ngrok-free.dev"],
  },
  build: {
    outDir: "build",
  },
});
