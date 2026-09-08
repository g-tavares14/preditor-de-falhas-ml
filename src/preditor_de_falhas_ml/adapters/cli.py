"""Controller de terminal: argparse, ambiente e apresentação."""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from preditor_de_falhas_ml.adapters.atlas import AtlasGateway
from preditor_de_falhas_ml.adapters.file_dataset import FileDataset
from preditor_de_falhas_ml.application.collect import collect_measurement
from preditor_de_falhas_ml.application.create import create_measurement
from preditor_de_falhas_ml.application.ports import GatewayError
from preditor_de_falhas_ml.domain.ids import MeasurementId, ProbeId
from preditor_de_falhas_ml.domain.spec import (
    CountrySelection,
    MeasurementSpec,
    ProbeIdSelection,
    ResultFilters,
)

DEFAULT_TARGET = "8.8.8.8"
DEFAULT_AF = 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m preditor_de_falhas_ml",
        description="Consulte créditos e medições de ping do RIPE Atlas.",
        epilog=(
            "Defina RIPE_ATLAS_API_KEY para criar medições ou consultar créditos. "
            "Consultas de resultados públicos não exigem chave."
        ),
    )
    operations = parser.add_subparsers(dest="operation", title="operações")
    operations.add_parser("credits", help="Consultar o saldo de créditos.")
    creation = operations.add_parser(
        "create-sample",
        help="Criar uma medição de ping (default: 8.8.8.8 IPv4 one-off).",
        description=(
            "Cria um ping ICMP. Sem --interval/--duration a medição é pontual. "
            "A criação consome créditos."
        ),
    )
    selection = creation.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--country-code", help="Código do país com duas letras, como BR."
    )
    selection.add_argument(
        "--probe-ids", nargs="+", type=int, help="IDs distintos de probes específicas."
    )
    creation.add_argument(
        "--probe-count", type=int, help="Quantidade positiva de probes do país (1)."
    )
    creation.add_argument(
        "--packets", type=int, default=16, help="Pacotes por probe, de 1 a 16 (16)."
    )
    creation.add_argument(
        "--target", default=DEFAULT_TARGET, help="Alvo da medição (8.8.8.8)."
    )
    creation.add_argument(
        "--af",
        type=int,
        default=DEFAULT_AF,
        dest="address_family",
        help="Família: 4 ou 6 (4).",
    )
    creation.add_argument(
        "--interval", type=int, help="Intervalo em segundos (recorrente)."
    )
    creation.add_argument(
        "--duration", type=int, help="Duração em segundos (recorrente)."
    )
    results = operations.add_parser(
        "results", help="Consultar os resultados disponíveis de uma medição."
    )
    results.add_argument(
        "measurement_id", type=int, help="ID inteiro positivo retornado na criação."
    )
    features = operations.add_parser(
        "features",
        help="Calcular e registrar X = [latência, perda, jitter] por probe e instante.",
        description="Consulta resultados, preserva o histórico e calcula os atributos em JSON.",
    )
    features.add_argument(
        "measurement_id", type=int, help="ID inteiro positivo de uma medição de ping."
    )
    dataset = operations.add_parser(
        "dataset", help="Coletar ou reconstruir o dataset de X."
    )
    dataset_operations = dataset.add_subparsers(dest="dataset_operation", required=True)
    collect = dataset_operations.add_parser(
        "collect", help="Importar uma ou mais medições existentes."
    )
    collect.add_argument(
        "measurement_ids",
        nargs="+",
        type=int,
        help="IDs inteiros positivos de medições.",
    )
    rebuild = dataset_operations.add_parser(
        "rebuild", help="Reconstruir CSV a partir do histórico, sem rede."
    )
    for operation in (creation, results, features, collect, rebuild):
        operation.add_argument(
            "--output-dir",
            type=Path,
            default=Path("data"),
            help="Diretório do histórico e do CSV (data).",
        )
    for operation in (results, features, collect):
        operation.add_argument(
            "--probe-id", type=int, help="Filtrar resultados por probe."
        )
        operation.add_argument(
            "--start", type=int, help="Início Unix (segundos) da consulta."
        )
        operation.add_argument(
            "--stop", type=int, help="Fim Unix (segundos) da consulta."
        )
    return parser


def _filters(args: argparse.Namespace) -> ResultFilters:
    return ResultFilters(
        probe_id=None
        if getattr(args, "probe_id", None) is None
        else ProbeId(args.probe_id),
        start=getattr(args, "start", None),
        stop=getattr(args, "stop", None),
    )


def _spec(args: argparse.Namespace) -> MeasurementSpec:
    if args.probe_ids is not None:
        selection: CountrySelection | ProbeIdSelection = ProbeIdSelection(
            tuple(args.probe_ids)
        )
    else:
        selection = CountrySelection(
            args.country_code, 1 if args.probe_count is None else args.probe_count
        )
    return MeasurementSpec(
        target=args.target,
        address_family=args.address_family,
        selection=selection,
        packets=args.packets,
        interval=args.interval,
        duration=args.duration,
    )


def _api_key(*, required: bool) -> str | None:
    key = os.environ.get("RIPE_ATLAS_API_KEY")
    if key:
        return key
    if required:
        raise ValueError(
            "RIPE_ATLAS_API_KEY ausente ou vazia. Defina a chave no ambiente "
            "ou carregue seu .env com uv run --env-file .env."
        )
    return None


def _print_rows(rows: Sequence[object]) -> None:
    print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))


def main(argv: Sequence[str] | None = None) -> int:
    """Executa uma operação e retorna 0 em sucesso ou 1 em falha operacional."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.operation is None:
        parser.print_help()
        return 0

    store = FileDataset(getattr(args, "output_dir", Path("data")))
    if args.operation == "dataset" and args.dataset_operation == "rebuild":
        try:
            report = store.rebuild()
        except (OSError, ValueError) as error:
            print(
                f"Erro ao reconstruir o dataset: {error}. Confira o diretório e o histórico.",
                file=sys.stderr,
            )
            return 1
        print(json.dumps(report.summary(), ensure_ascii=False, indent=2))
        return 1 if report.rejected else 0

    needs_key = args.operation in {"credits", "create-sample"}
    try:
        api_key = _api_key(required=needs_key)
        if args.operation != "credits":
            store.prepare()
        with AtlasGateway(api_key) as atlas:
            if args.operation == "credits":
                print(f"Créditos: {atlas.get_credits()}")
                return 0
            if args.operation == "create-sample":
                measurement_id = create_measurement(atlas, store, _spec(args))
                print(f"ID da medição: {measurement_id.value}")
                return 0
            filters = _filters(args)
            if args.operation == "dataset":
                summaries = []
                failed = False
                for value in dict.fromkeys(args.measurement_ids):
                    identifier = MeasurementId(value)
                    try:
                        report = collect_measurement(atlas, store, identifier, filters)
                    except (GatewayError, ValueError) as error:
                        print(
                            f"Erro na medição {value}: {error}",
                            file=sys.stderr,
                        )
                        summaries.append(
                            {"measurement_id": value, "state": "request_failed"}
                        )
                        failed = True
                        continue
                    for rejection in report.rejections:
                        print(
                            f"Registro rejeitado: {rejection.reason}", file=sys.stderr
                        )
                    summaries.append(report.summary())
                    failed |= report.rejected > 0
                print(json.dumps(summaries, ensure_ascii=False, indent=2))
                return int(failed)

            report = collect_measurement(
                atlas, store, MeasurementId(args.measurement_id), filters
            )
            for rejection in report.rejections:
                print(f"Registro rejeitado: {rejection.reason}", file=sys.stderr)
            if args.operation == "features":
                _print_rows([row.as_row() for row in report.observations])
            else:
                _print_rows(list(report.raw_results))
            return 1 if report.rejected else 0
    except GatewayError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(
            f"Erro no armazenamento: {error}. Confira permissões e espaço no diretório "
            "do dataset. Se um ID de medição já foi exibido, guarde-o e não repita a criação.",
            file=sys.stderr,
        )
        return 1
    return 0
