# Como contribuir

Este projeto é desenvolvido em conjunto pelas disciplinas de Estruturas de Dados II (ED2), Redes de Computadores e Análise e Projeto de Sistemas (APS). Os documentos são compartilhados entre as disciplinas e ficam em `docs/`, sem separação por matéria.

## Regra principal

- A `main` é protegida no GitHub.
- Não se trabalha diretamente na `main`.
- Toda alteração entra por uma branch e um Pull Request.
- O Pull Request precisa de pelo menos uma aprovação.
- Conversas do Pull Request devem ser resolvidas antes do merge.
- Administradores também ficam sujeitos à proteção.
- Force push e exclusão da `main` são desabilitados.

## Branches

Use nomes curtos, em minúsculas, com o objetivo da alteração:

```text
feat/<nome-da-entrega>
fix/<nome-do-ajuste>
docs/<nome-da-documentacao>
chore/<nome-da-configuracao>
```

Exemplo:

```text
docs/memorando
```

## Fluxo recomendado

```bash
git switch main
git pull --ff-only origin main
git switch -c feat/nome-da-entrega
```

Faça os commits na branch, envie-a ao GitHub e abra um Pull Request para `main`:

```bash
git push -u origin feat/nome-da-entrega
```

Após a revisão e o merge, atualize sua cópia local da `main` antes de iniciar a próxima entrega.

## Documentação compartilhada

Materiais que servem para mais de uma disciplina devem permanecer em `docs/`, organizados pelo tipo de artefato ou pelo assunto do projeto. A disciplina é identificada pela branch e pelo Pull Request, não por uma pasta separada.
