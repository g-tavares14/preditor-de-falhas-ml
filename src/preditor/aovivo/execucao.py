"""Orquestra o comando `aovivo`: conferências, preparo (sorteio e baseline) e o laço (SPEC-ao-vivo.md)."""

from argparse import Namespace

from preditor.aovivo import conferencia, parametros
from preditor.aovivo.atlas import ClienteAtlas
from preditor.aovivo.servico import ServicoAoVivo, ler_estado, preparar
from preditor.visualizacao.modelo_exportado import ModeloExportado


class ExecucaoAoVivo:
    def executar(self, argumentos: Namespace) -> None:
        cliente = ClienteAtlas()

        if argumentos.conferir:
            # As duas conferências, sem subir o serviço: o motor contra o Gold e o leitor contra o Silver (esta pede a API).
            conferencia.motor_contra_o_gold()
            conferencia.leitor_contra_o_silver(cliente)
            return

        # Toda partida confere o motor contra o Gold (offline, poucos segundos): se a cópia em pandas divergisse do Spark,
        # a previsão ao vivo não seria a do modelo que foi medido.
        if not argumentos.sem_conferir:
            conferencia.motor_contra_o_gold()

        # O SHA-256 do `.joblib` é conferido contra o LEIA-ME antes de abri-lo (um pickle executa código ao abrir).
        exportado = ModeloExportado.ler()

        if argumentos.recomecar:
            self._apagar_saidas()
        estado = ler_estado()
        if estado is None:
            estado = preparar(cliente, exportado, argumentos.quantas, self._paises(argumentos.paises), argumentos.retroativo_horas)
        else:
            if estado["modelo_sha256"] != exportado.sha256:
                raise SystemExit("O modelo mudou desde que o estado foi gravado. Use --recomecar para sortear e calcular o baseline de novo.")
            print(f"Retomando o estado de {estado['criado_em']}: {len(estado['sondas'])} sondas, T0 fixo (--recomecar apaga e recomeça).")

        servico = ServicoAoVivo(cliente, exportado, estado)
        print(
            f"Ao vivo com {len(servico.utilizaveis)} fluxos de {len(servico.sondas)} sondas; uma consulta por "
            f"{parametros.INTERVALO_CONSULTA_S} s. Página: uv run python -m preditor servir  →  http://127.0.0.1:8000/?ao-vivo"
        )
        servico.rodar(argumentos.ciclos)

    @staticmethod
    def _paises(texto: str | None) -> tuple[str, ...]:
        return tuple(pais.strip().upper() for pais in texto.split(",") if pais.strip()) if texto else parametros.PAISES_PADRAO

    @staticmethod
    def _apagar_saidas() -> None:
        """Apaga só os arquivos que o próprio serviço grava (nada de `data/modelo/`, nada do teste)."""
        for arquivo in (
            parametros.ARQUIVO_ESTADO, parametros.ARQUIVO_HISTORICO, parametros.ARQUIVO_MEDICOES,
            parametros.ARQUIVO_PREVISOES, parametros.ARQUIVO_RESUMO, parametros.ARQUIVO_PAGINA,
        ):
            arquivo.unlink(missing_ok=True)
