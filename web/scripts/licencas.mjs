// licencas.mjs: junta o aviso de licença de cada pacote do npm que vai no site (as dependências de produção, com as transitivas) num
// arquivo só: `dist/licencas-de-terceiros.txt`. Os pacotes ISC e MIT exigem manter o aviso de copyright e a permissão junto das cópias, e o
// minificador do Vite não leva os comentários de licença para o JavaScript empacotado.
//
// Uso: `node scripts/licencas.mjs [arquivo-de-saida]` (o `npm run build` já o chama).

import { execSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const saida = process.argv[2] ?? "dist/licencas-de-terceiros.txt";

/** Todos os pacotes de produção (nome → versão), percorrendo a árvore que o npm resolve. */
function pacotesDeProducao() {
  const arvore = JSON.parse(execSync("npm ls --omit=dev --all --json", { encoding: "utf-8", maxBuffer: 1 << 26 }));
  const achados = new Map();
  (function visitar(dependencias) {
    for (const [nome, info] of Object.entries(dependencias ?? {})) {
      achados.set(nome, info.version);
      visitar(info.dependencies);
    }
  })(arvore.dependencies);
  return [...achados.entries()].sort(([a], [b]) => a.localeCompare(b));
}

const blocos = [];
for (const [nome, versao] of pacotesDeProducao()) {
  const pasta = join("node_modules", nome);
  if (!existsSync(pasta)) {
    throw new Error(`o pacote ${nome} não está em node_modules (rode \`npm ci\`)`);
  }
  const { license: licenca } = JSON.parse(readFileSync(join(pasta, "package.json"), "utf-8"));
  const arquivo = readdirSync(pasta).find((f) => /^(license|licence|copying)(\.|$)/i.test(f));
  const texto = arquivo ? readFileSync(join(pasta, arquivo), "utf-8").trim() : "(o pacote não traz um arquivo de licença; licença declarada no package.json)";
  blocos.push(`${"=".repeat(100)}\n${nome}@${versao}  (${licenca})\n${"=".repeat(100)}\n\n${texto}\n`);
}

writeFileSync(saida, `Licenças dos pacotes de terceiros empacotados neste site (gerado por web/scripts/licencas.mjs).\n\n${blocos.join("\n")}`);
console.log(`licenças de ${blocos.length} pacotes → ${saida}`);
