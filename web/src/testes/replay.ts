// Ajuda dos testes: lê o `replay.json` de verdade (o mesmo que a página carrega), uma vez por arquivo de teste.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { Replay } from "../tipos";

const CAMINHO = fileURLToPath(new URL("../../public/dados/replay.json", import.meta.url));

export function lerReplay(): Replay {
  return JSON.parse(readFileSync(CAMINHO, "utf-8")) as Replay;
}
