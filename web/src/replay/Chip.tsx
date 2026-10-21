// Chip.tsx: a etiqueta de texto de uma classe, com a cor dela (`chip-ok`, `chip-risco` e `chip-falha` vêm do CSS). A cor e o texto
// andam juntos: nunca só cor.

import { NOME_DA_CLASSE } from "../logica/comum";
import type { Classe } from "../tipos";

export function Chip({ classe }: { classe: Classe }) {
  return <span className={`chip chip-${classe.toLowerCase()}`}>{NOME_DA_CLASSE[classe]}</span>;
}
