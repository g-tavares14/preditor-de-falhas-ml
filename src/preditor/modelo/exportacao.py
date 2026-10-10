"""Exporta o modelo escolhido pela comparação e a árvore ajustada, verificados em processo novo (SPEC-comparacao-modelos.md).

`exportar` lê `escolha.json` (gravado pelo `comparar`), refaz o modelo escolhido e a árvore ajustada só com o treino, e
confere que o refeito dá o F1 medido. Grava os dois `.joblib` (dicionários só com objetos do scikit-learn, do XGBoost e
da biblioteca padrão) numa pasta temporária, abre cada um num processo NOVO, sem o pacote `preditor`, roda o exemplo de
uso a partir de outra pasta, e só então copia tudo para `data/modelo/exportado/` e grava o LEIA-ME. Se uma checagem
falha, nada vai para a pasta final.
"""

import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import joblib
import pandas as pd

from preditor import config
from preditor.modelo.arvore import ArvoreBase
from preditor.modelo.avaliacao import Avaliacao
from preditor.modelo.boosting import CLASSE, Boosting
from preditor.modelo.dados import DadosModelo
from preditor.modelo.floresta import Floresta

# Bibliotecas cujas versões vão para o pacote e para o LEIA-ME: sem elas a professora não sabe se o arquivo abre.
BIBLIOTECAS = ["scikit-learn", "xgboost", "numpy", "pandas", "joblib"]

# Roda num processo NOVO, com `python -I`. Abre cada `.joblib`, prevê o X (com NaN) e uma medição toda vazia, e devolve
# tudo em JSON. A checagem `importou_preditor` mostra se alguma coisa do pacote `preditor` entrou na memória.
SCRIPT_RECARGA = '''import json
import sys

import joblib
import pandas as pd

X = pd.read_parquet(sys.argv[1])
resposta = {"previsoes": {}, "sem_valores": {}}
for caminho in sys.argv[2:]:
    pacote = joblib.load(caminho)
    modelo, colunas, rotulos = pacote["modelo"], pacote["colunas"], pacote["rotulos_do_modelo"]

    def classes(linhas):
        previsto = list(modelo.predict(linhas[colunas]))
        return previsto if rotulos is None else [rotulos[int(codigo)] for codigo in previsto]

    resposta["previsoes"][caminho] = classes(X)
    # Medição sem nenhum valor (tudo ausente): o modelo tem de aceitar e devolver uma das classes.
    vazia = pd.DataFrame([{coluna: float("nan") for coluna in colunas}])
    resposta["sem_valores"][caminho] = classes(vazia)
resposta["importou_preditor"] = any(nome == "preditor" or nome.startswith("preditor.") for nome in sys.modules)
print(json.dumps(resposta))
'''

# Exemplo que a professora roda: lê os `.joblib` ao lado do próprio arquivo, então funciona de qualquer pasta.
EXEMPLO_DE_USO = '''"""Exemplo de uso do modelo exportado do preditor de degradação de rede (ver LEIA-ME.md).

Roda de qualquer pasta: `python exemplo_de_uso.py`. Precisa de scikit-learn, pandas e joblib (e de xgboost, se o
modelo for o XGBoost). NÃO precisa do pacote `preditor`. Os valores abaixo são inventados, só para mostrar o formato.

Atenção: um .joblib é um pickle, e abrir um pickle executa código. Abra só arquivo de fonte confiável e confira o
SHA-256 no LEIA-ME.md antes.
"""

from pathlib import Path

import joblib
import pandas as pd

PASTA = Path(__file__).resolve().parent
pacote = joblib.load(PASTA / "modelo_final.joblib")
colunas = pacote["colunas"]

# Três medições. Quem não tem um valor simplesmente não o informa: o modelo aceita o ausente (NaN).
medicoes = pd.DataFrame(
    [
        {"z_robusto": 0.3, "aumento_pct": 2.0, "jitter_relativo": 1.1, "perda_pct": 0.0, "timeout_atual": 0,
         "n5_timeout": 0, "n5_aumento80": 0, "n5_moderado": 0, "min5_z": -0.5, "media5_z": -0.1},
        {"z_robusto": 6.0, "aumento_pct": 45.0, "jitter_relativo": 2.0, "perda_pct": 0.0, "timeout_atual": 0,
         "n5_timeout": 0, "n5_aumento80": 0, "n5_moderado": 1, "min5_z": 0.1, "media5_z": 0.5},
        {"perda_pct": 100.0, "timeout_atual": 1, "n5_timeout": 2, "n5_aumento80": 0, "n5_moderado": 2},
    ],
    columns=colunas,
)
nomes = ["Medição estável", "Pico de agora", "Sem RTT nesta medição"]

previsto = pacote["modelo"].predict(medicoes[colunas])
if pacote["rotulos_do_modelo"] is not None:
    previsto = [pacote["rotulos_do_modelo"][int(codigo)] for codigo in previsto]

print(f"Modelo: {pacote['familia']} (formato {pacote['formato']}, semente {pacote['semente']})")
print("A previsão é a classe da 3ª medição à frente do mesmo caminho (cerca de 12 minutos depois):")
for nome, classe in zip(nomes, previsto):
    print(f"  {nome:<24} -> {classe}")
'''


class ExportacaoModelo:
    def executar(self) -> None:
        self._exigir_comparacao()
        escolha = json.loads(config.ARQUIVO_ESCOLHA.read_text(encoding="utf-8"))
        familia = escolha["modelo"]
        # Sem o Gold (ou com um Gold sem as colunas novas), `DadosModelo` diz qual comando rodar antes.
        dados = DadosModelo().carregar()
        validacao = config.BLOCO_VALIDACAO
        X = dados.x_ajustado(validacao)
        y = dados.y[validacao]
        print(f"Exportação: o modelo escolhido pela regra da comparação é {familia}.")
        print(f"  treino = {dados.resumo[config.BLOCO_TREINO]['n']} medições (o único bloco usado para treinar)")

        # 1. Refaz o modelo escolhido e a árvore ajustada, só com o treino e com os parâmetros gravados.
        rotulos = self._rotulos(familia)
        modelo = self._refazer(familia, escolha["parametros"], dados)
        arvore, gravada = self._refazer_arvore(dados)

        # 2. O refeito tem de ser o medido: mesmo F1 na validação que o `comparar` e o `ajuste` gravaram.
        previsto_modelo = self._prever(modelo, X, rotulos)
        previsto_arvore = self._prever(arvore, X, None)
        self._verificar_refeitos(familia, modelo, arvore, gravada, escolha, previsto_modelo, previsto_arvore, y, dados)

        # 3. Os dicionários que vão para os arquivos, e a verificação em processo novo, tudo numa pasta temporária.
        pacote_modelo = self._pacote(familia, modelo, escolha["parametros"], rotulos, dados)
        pacote_arvore = self._pacote(config.MODELO_AJUSTADA, arvore, gravada, None, dados)
        with tempfile.TemporaryDirectory() as pasta_temporaria:
            temporaria = Path(pasta_temporaria)
            caminhos = {
                "modelo": temporaria / config.ARQUIVO_MODELO_FINAL.name,
                "arvore": temporaria / config.ARQUIVO_ARVORE_EXPORTADA.name,
            }
            joblib.dump(pacote_modelo, caminhos["modelo"])
            joblib.dump(pacote_arvore, caminhos["arvore"])
            self._verificar_processo_novo(
                temporaria, X, {caminhos["modelo"]: previsto_modelo, caminhos["arvore"]: previsto_arvore}
            )
            exemplo = temporaria / config.ARQUIVO_EXEMPLO_DE_USO.name
            exemplo.write_text(EXEMPLO_DE_USO, encoding="utf-8")
            self._rodar_exemplo_de_outra_pasta(exemplo, temporaria)

            # 4. Tudo conferido: copia para a pasta final e grava o LEIA-ME com o SHA-256 do que foi copiado.
            config.EXPORTADO.mkdir(parents=True, exist_ok=True)
            for origem, destino in (
                (caminhos["modelo"], config.ARQUIVO_MODELO_FINAL),
                (caminhos["arvore"], config.ARQUIVO_ARVORE_EXPORTADA),
                (exemplo, config.ARQUIVO_EXEMPLO_DE_USO),
            ):
                shutil.copyfile(origem, destino)
        ic = pd.read_csv(config.ARQUIVO_IC_PAREADO)
        config.ARQUIVO_LEIA_ME.write_text(
            self._leia_me(familia, escolha, gravada, dados, ic), encoding="utf-8"
        )
        self._imprimir_arquivos()
        print("\nExportação: todas as checagens passaram. O teste continua fechado.")

    # ----------------------------------------------------------------------------------------------------------------
    # Entrada
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _exigir_comparacao() -> None:
        """A exportação lê a escolha do `comparar`: sem ela, pede para rodá-lo antes."""
        necessarios = (
            config.ARQUIVO_ESCOLHA, config.ARQUIVO_BUSCA_FLORESTA, config.ARQUIVO_BUSCA_BOOSTING,
            config.ARQUIVO_COMPARACAO_MODELOS, config.ARQUIVO_IC_PAREADO, config.ARQUIVO_ARVORE_AJUSTADA,
            config.ARQUIVO_METRICAS_AJUSTE,
        )
        faltando = [str(arquivo) for arquivo in necessarios if not arquivo.exists()]
        if faltando:
            raise SystemExit(
                f"Não encontrei {', '.join(faltando)}.\n"
                "Rode antes: uv run python -m preditor comparar"
            )

    # ----------------------------------------------------------------------------------------------------------------
    # Refazer os modelos (só com o treino)
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _rotulos(familia: str) -> dict[int, str] | None:
        """O XGBoost devolve códigos 0, 1, 2; o arquivo guarda o mapa para o texto. Os outros já devolvem o texto."""
        return {codigo: classe for codigo, classe in enumerate(CLASSE)} if familia == config.MODELO_BOOSTING else None

    @staticmethod
    def _refazer(familia: str, parametros: dict, dados: DadosModelo):
        """Treina de novo o modelo escolhido, com os mesmos parâmetros e a mesma semente (o mesmo `_ajustar` da busca)."""
        if familia == config.MODELO_FLORESTA:
            return Floresta._ajustar(
                dados, int(parametros["n_estimators"]), int(parametros["max_depth"]), int(parametros["min_samples_leaf"])
            )
        if familia == config.MODELO_BOOSTING:
            return Boosting._ajustar(
                dados, int(parametros["n_estimators"]), float(parametros["learning_rate"]), int(parametros["max_depth"])
            )
        if familia == config.MODELO_AJUSTADA:
            return ArvoreBase._ajustar(
                dados, int(parametros["max_depth_pedido"]), int(parametros["min_samples_leaf_pedido"]),
                ajustado=True, criterio=parametros["criterio"], peso=parametros["class_weight"],
            )
        raise SystemExit(f"Não sei exportar a família {familia!r}.")

    @staticmethod
    def _refazer_arvore(dados: DadosModelo):
        """A árvore ajustada de `arvore_ajustada.json` (a adotada na Tarefa 4), treinada de novo só com o treino."""
        gravada = json.loads(config.ARQUIVO_ARVORE_AJUSTADA.read_text(encoding="utf-8"))
        arvore = ArvoreBase._ajustar(
            dados, int(gravada["max_depth_pedido"]), int(gravada["min_samples_leaf_pedido"]),
            ajustado=True, criterio=gravada["criterio"], peso=gravada["class_weight"],
        )
        return arvore, gravada

    @staticmethod
    def _prever(modelo, X: pd.DataFrame, rotulos: dict[int, str] | None) -> list[str]:
        """Classe de cada linha de X como texto: o mesmo cálculo que o arquivo faz quando é aberto."""
        previsto = modelo.predict(X)
        if rotulos is not None:
            previsto = [rotulos[int(codigo)] for codigo in previsto]
        return [str(classe) for classe in previsto]

    # ----------------------------------------------------------------------------------------------------------------
    # Pacote e checagens
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _pacote(familia: str, modelo, parametros: dict, rotulos: dict[int, str] | None, dados: DadosModelo) -> dict:
        """O dicionário gravado: o modelo, as 10 colunas na ordem, as classes, a semente, as versões e os parâmetros."""
        versoes = {"python": platform.python_version()}
        versoes.update({nome: importlib.metadata.version(nome) for nome in BIBLIOTECAS})
        return {
            "formato": config.FORMATO_EXPORTADO,
            "familia": familia,
            "modelo": modelo,
            "colunas": DadosModelo.colunas_ajustadas(),
            "classes": list(config.CLASSES),
            "rotulos_do_modelo": rotulos,  # None: o modelo já devolve o texto; dict: o modelo devolve o código
            "semente": config.SEMENTE,
            "parametros": parametros,
            "versoes": versoes,
            "treino": f"{dados.resumo[config.BLOCO_TREINO]['n']} medições do bloco de treino (sem validação nem teste)",
            "ausentes": "valores ausentes (NaN) são aceitos e não são preenchidos",
        }

    @staticmethod
    def _verificar_refeitos(familia, modelo, arvore, gravada, escolha, previsto_modelo, previsto_arvore, y, dados) -> None:
        """O que foi refeito é o que foi medido: mesmos parâmetros, mesmas 10 colunas e o F1 da validação gravado."""
        casa = 10**-config.CASAS_CSV  # os CSVs e o JSON arredondam: uma unidade da última casa de folga
        validacao = config.BLOCO_VALIDACAO
        colunas = DadosModelo.colunas_ajustadas()

        f1_modelo = Avaliacao.medir(y, pd.Series(previsto_modelo, index=y.index), bloco=validacao).f1_macro
        assert abs(f1_modelo - escolha["f1_macro_escolhido"]) <= casa, (
            f"{familia}: o refeito dá F1 {f1_modelo:.6f}, e a escolha gravou {escolha['f1_macro_escolhido']:.6f}"
        )
        if familia == config.MODELO_FLORESTA:
            assert list(modelo.feature_names_in_) == colunas, "a floresta refeita tem outras colunas"
        if familia == config.MODELO_BOOSTING:
            assert list(modelo.feature_names_in_) == colunas, "o XGBoost refeito tem outras colunas"

        # A árvore ajustada refeita: o F1 da validação é o de `metricas_ajuste.csv` e os parâmetros são os do JSON.
        f1_arvore = Avaliacao.medir(y, pd.Series(previsto_arvore, index=y.index), bloco=validacao).f1_macro
        gravados = pd.read_csv(config.ARQUIVO_METRICAS_AJUSTE)
        f1_gravado = gravados[(gravados["modelo"] == config.MODELO_AJUSTADA) & (gravados["metrica"] == "f1_macro")]
        assert abs(f1_arvore - f1_gravado["valor"].iloc[0]) <= casa, "a árvore ajustada refeita não dá o F1 de metricas_ajuste.csv"
        assert (arvore.criterion, arvore.max_depth, arvore.min_samples_leaf) == (
            gravada["criterio"], gravada["max_depth_pedido"], gravada["min_samples_leaf_pedido"]
        ), "a árvore ajustada refeita não tem os parâmetros de arvore_ajustada.json"
        assert arvore.class_weight == gravada["class_weight"], "peso de classe da árvore refeita diferente do JSON"
        assert list(arvore.feature_names_in_) == colunas, "a árvore ajustada refeita tem outras colunas"

    @staticmethod
    def _verificar_processo_novo(temporaria: Path, X: pd.DataFrame, previstos: dict[Path, list[str]]) -> None:
        """Abre cada arquivo num processo novo: reproduz as previsões, aceita NaN, só devolve as 3 classes, sem `preditor`."""
        X.to_parquet(temporaria / "X.parquet")  # ausente vira nulo no Parquet e volta como NaN
        (temporaria / "recarga.py").write_text(SCRIPT_RECARGA, encoding="utf-8")
        caminhos = [str(caminho) for caminho in previstos]
        processo = subprocess.run(
            [sys.executable, "-I", str(temporaria / "recarga.py"), str(temporaria / "X.parquet"), *caminhos],
            cwd=temporaria, capture_output=True, text=True, check=False,
        )
        assert processo.returncode == 0, f"a recarga em processo novo falhou:\n{processo.stderr}"
        resposta = json.loads(processo.stdout.strip().splitlines()[-1])

        assert not resposta["importou_preditor"], "abrir o arquivo importou o pacote preditor"
        for caminho, previsto in previstos.items():
            nome = caminho.name
            recarregado = resposta["previsoes"][str(caminho)]
            assert recarregado == previsto, f"{nome}: em processo novo, as previsões da validação não são as mesmas"
            assert set(recarregado) <= set(config.CLASSES), f"{nome}: devolveu classe fora de OK/RISCO/FALHA"
            sem_valores = resposta["sem_valores"][str(caminho)]
            assert len(sem_valores) == 1 and set(sem_valores) <= set(config.CLASSES), (
                f"{nome}: a medição sem valores não devolveu uma das três classes"
            )
            # O arquivo não cita o pacote do projeto em lugar nenhum (um pickle que aponta para o `preditor` falharia fora dele).
            assert b"preditor" not in caminho.read_bytes(), f"{nome} referencia o pacote preditor"

    @staticmethod
    def _rodar_exemplo_de_outra_pasta(exemplo: Path, temporaria: Path) -> None:
        """O exemplo roda a partir de outra pasta e imprime uma classe válida para cada medição."""
        outra = temporaria / "outra_pasta"
        outra.mkdir()
        processo = subprocess.run(
            [sys.executable, str(exemplo)], cwd=outra, capture_output=True, text=True, check=False
        )
        assert processo.returncode == 0, f"o exemplo de uso falhou fora da pasta do arquivo:\n{processo.stderr}"
        classes = [linha.split("->")[-1].strip() for linha in processo.stdout.splitlines() if "->" in linha]
        assert len(classes) == 3 and set(classes) <= set(config.CLASSES), f"exemplo devolveu {classes}"

    # ----------------------------------------------------------------------------------------------------------------
    # LEIA-ME e impressão
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _leia_me(familia: str, escolha: dict, gravada: dict, dados: DadosModelo, ic: pd.DataFrame) -> str:
        """O LEIA-ME: o que é, como abrir com segurança, as colunas, as classes, as versões e os limites."""
        arquivos = [config.ARQUIVO_MODELO_FINAL, config.ARQUIVO_ARVORE_EXPORTADA, config.ARQUIVO_EXEMPLO_DE_USO]
        tabela = "\n".join(
            f"| `{arquivo.name}` | {_tamanho(arquivo)} | `{_sha256(arquivo)}` |" for arquivo in arquivos
        )
        versoes = {"python": platform.python_version()}
        versoes.update({nome: importlib.metadata.version(nome) for nome in BIBLIOTECAS})
        lista_versoes = "\n".join(f"- {nome}: {versao}" for nome, versao in versoes.items())
        colunas = "\n".join(f"{i}. `{coluna}`: {DESCRICAO_COLUNAS[coluna]}" for i, coluna in enumerate(DadosModelo.colunas_ajustadas(), 1))
        parametros = "\n".join(f"  - `{chave}`: {valor}" for chave, valor in escolha["parametros"].items())
        candidatas = "\n".join(
            f"  - {c['modelo']}: F1 macro {_br(c['f1_macro_validacao'], 6)} "
            f"({'dentro' if c['dentro_da_tolerancia'] else 'fora'} da tolerância de {_br(escolha['tolerancia_escolha'], 3)})"
            for c in escolha["candidatas"]
        )
        mapa = (
            "O modelo devolve um código (0, 1 ou 2) e o arquivo traz o mapa `rotulos_do_modelo`."
            if familia == config.MODELO_BOOSTING
            else "O modelo devolve o texto da classe direto (`rotulos_do_modelo` é `None`)."
        )
        return f"""# Modelo exportado: preditor de degradação de rede

Gerado por `uv run python -m preditor exportar` (SPEC-comparacao-modelos.md, "Exportação"). Todos os números deste
arquivo vêm de `data/modelo/comparacao/` ou da própria exportação. Nada do teste (Tarefa 5) aparece aqui.

## O que há nesta pasta

| Arquivo | Tamanho | SHA-256 |
|---|---|---|
{tabela}

- `modelo_final.joblib`: o modelo que a regra escolheu ({familia}), treinado só com o bloco de treino.
- `arvore_ajustada.joblib`: a árvore ajustada da Tarefa 4 (com peso de classe), em arquivo à parte. Ela é legível: as
  regras em português estão em `data/modelo/regras_arvore_ajustada.txt`.
- `exemplo_de_uso.py`: um exemplo curto que roda de qualquer pasta.

## Antes de abrir: segurança

> **Um `.joblib` é um pickle, e abrir um pickle executa código.** Só abra arquivos de fonte confiável. Antes de abrir,
> confira o SHA-256 da tabela:
>
> - macOS: `shasum -a 256 modelo_final.joblib`
> - Linux: `sha256sum modelo_final.joblib`

## O modelo escolhido

- Família: **{familia}**, pela regra da comparação: entre as candidatas, as que estão a até
  {_br(escolha['tolerancia_escolha'], 3)} do maior F1 macro da validação, vence a mais simples (ordem: árvore, Random
  Forest, XGBoost).
{candidatas}
- F1 macro na validação: **{_br(escolha['f1_macro_escolhido'], 6)}**. A persistência, na mesma validação, tem
  {_br(escolha['f1_macro_persistencia'], 6)}. O modelo supera a persistência: {'sim' if escolha['supera_persistencia'] else 'não'}.
- Parâmetros (todos gravados em `modelo_final.joblib`):
{parametros}
- Treino: {_milhares(dados.resumo[config.BLOCO_TREINO]['n'])} medições. Validação:
  {_milhares(dados.resumo[config.BLOCO_VALIDACAO]['n'])} (só para escolher e medir). Teste: fechado.

## As colunas de entrada, na ordem

O modelo espera exatamente estas 10 colunas, nesta ordem (o arquivo guarda a lista em `colunas`):

{colunas}

Nenhuma coluna de região, país, IP, rota ou RTT absoluto entra no modelo (a RFC proíbe).

## Valores ausentes

Se uma medição não tem algum valor (por exemplo, o RTT não veio porque a sonda não respondeu), **deixe o valor
ausente**. O modelo aceita e não preenche: trocar por zero daria uma medição que não aconteceu. O `exemplo_de_uso.py` mostra
uma medição assim.

## A saída

{mapa}
A classe é a da **3ª medição à frente** do mesmo caminho, cerca de 12 minutos depois: OK, RISCO ou FALHA. Não é uma
leitura do que acontece agora.

## Versões usadas (para abrir, precisa de versões iguais ou compatíveis)

{lista_versoes}

Outra versão do scikit-learn ou do XGBoost pode não abrir o arquivo, ou mudar as previsões. Se não abrir, confira a
versão acima.

## Como usar

```
python exemplo_de_uso.py
```

Precisa de scikit-learn, pandas e joblib (e de xgboost, se o modelo for o XGBoost). **Não precisa do pacote
`preditor`**: o arquivo só contém objetos dessas bibliotecas e da biblioteca padrão.

## Verificação feita na exportação

- Abrir `modelo_final.joblib` e `arvore_ajustada.joblib` em um processo novo reproduz exatamente as previsões da
  validação ({_milhares(dados.resumo[config.BLOCO_VALIDACAO]['n'])} medições).
- Uma medição sem nenhum valor é aceita e recebe uma das três classes.
- Só saem OK, RISCO e FALHA.
- O exemplo roda a partir de outra pasta.

## Limites que valem para o modelo

- Todos os números são da validação. O teste (Tarefa 5) continua fechado.
- A validação foi usada para escolher o modelo **e** para compará-lo, o que deixa a comparação levemente otimista.
{_ganho(ic, familia, config.MODELO_PERSISTENCIA, 'a persistência')}
{_ganho(ic, familia, config.MODELO_AJUSTADA, 'a árvore ajustada')}
  (`ic_pareado.csv`: IC de 95 % por fluxo, 2.000 reamostras; o IC que cruza o zero não prova o ganho.)
- O rótulo é uma política: a regra 3 da RFC com piso de 30 % de aumento. O modelo aprende essa definição, não a falha
  real do equipamento.
- Só serve para fluxos com ficha de baseline (1.500 medições válidas no período inicial).
"""

    def _imprimir_arquivos(self) -> None:
        for arquivo in (config.ARQUIVO_MODELO_FINAL, config.ARQUIVO_ARVORE_EXPORTADA, config.ARQUIVO_LEIA_ME, config.ARQUIVO_EXEMPLO_DE_USO):
            print(f"Gravado: {arquivo} ({_tamanho(arquivo)}, SHA-256 {_sha256(arquivo)})")


def _ganho(ic: pd.DataFrame, familia: str, referencia: str, nome: str) -> str:
    """Uma linha do LEIA-ME sobre o ganho da família contra uma referência, com o veredito lido do `ic_pareado.csv`."""
    linha = ic[(ic["modelo"] == familia) & (ic["referencia"] == referencia)]
    if linha.empty:
        return f"- Ganho sobre {nome}: não está em `ic_pareado.csv`."
    r = linha.iloc[0]
    veredito = "tem prova (o intervalo não cruza o zero)" if r["exclui_zero"] else "não tem prova (o intervalo cruza o zero)"
    return (
        f"- Ganho sobre {nome}: diferença de F1 macro {_br(r['diferenca_f1'], 4, sinal=True)}, IC 95 % de "
        f"{_br(r['ic_inferior'], 4, sinal=True)} a {_br(r['ic_superior'], 4, sinal=True)}: {veredito}."
    )


def _br(valor: float, casas: int, sinal: bool = False) -> str:
    """Número com vírgula decimal, como nos textos do projeto (0,7457)."""
    texto = f"{valor:+.{casas}f}" if sinal else f"{valor:.{casas}f}"
    return texto.replace(".", ",")


def _milhares(n: int) -> str:
    """Inteiro com ponto de milhar (34.661)."""
    return f"{n:,}".replace(",", ".")


def _sha256(arquivo: Path) -> str:
    """SHA-256 do arquivo inteiro, como o `shasum -a 256` de macOS e o `sha256sum` de Linux."""
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


def _tamanho(arquivo: Path) -> str:
    """Tamanho em KB ou MB, para o LEIA-ME."""
    tamanho = arquivo.stat().st_size
    return f"{_br(tamanho / 1024 / 1024, 2)} MB" if tamanho >= 1024 * 1024 else f"{_br(tamanho / 1024, 1)} KB"


# Uma frase por coluna, para o LEIA-ME (o significado segue `gold/calculo_x/features.py` e a RFC §8.4).
DESCRICAO_COLUNAS = {
    "z_robusto": "quantos desvios típicos o RTT está acima do normal do caminho (mediana e MAD do próprio caminho).",
    "aumento_pct": "aumento percentual do RTT sobre a mediana do caminho.",
    "jitter_relativo": "jitter da medição dividido pelo jitter típico do caminho (acima de 3 é alteração).",
    "perda_pct": "percentual de pings perdidos na medição.",
    "timeout_atual": "1 se a medição teve timeout (nenhuma resposta), 0 se não.",
    "n5_timeout": "quantas das últimas 5 medições do caminho (incluindo esta) tiveram timeout.",
    "n5_aumento80": "quantas das últimas 5 medições tiveram aumento acima de 80 % sobre a mediana.",
    "n5_moderado": "quantas das últimas 5 medições tiveram alteração moderada (o critério de RISCO da RFC).",
    "min5_z": "o menor z_robusto das últimas 5 medições: alto só se o desvio se manteve nas 5.",
    "media5_z": "a média do z_robusto das últimas 5 medições.",
}
