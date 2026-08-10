import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // evalite_ui/server.py's mount_ui() serves from evalite_ui/dist/, i.e.
    // one directory above this ui/ project root.
    outDir: "../dist",
    emptyOutDir: true,
  },
});
