import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Em desenvolvimento o Vite serve o site em :5173 e repassa ao servidor Go (`cd servidor && go run ./cmd/preditor`, porta 5053) o que
// é dele: a API e o Swagger. `dados/replay.json` e `dados/aovivo.json` saem de `public/dados/` (onde o Python grava).
const SERVIDOR_GO = "http://localhost:5053";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": SERVIDOR_GO, "/swagger": SERVIDOR_GO } },
  build: { outDir: "dist", emptyOutDir: true },
  test: {
    environment: "node", // a lógica pura roda em Node; os testes de tela pedem jsdom com `// @vitest-environment jsdom`
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/testes/preparar.ts"],
  },
});
