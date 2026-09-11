"""Controller de terminal: argparse, ambiente e stdout."""

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from preditor_de_falhas_ml.atlas import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_TARGET,
    append_data,
    get_credits,
    get_data,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m preditor_de_falhas_ml",
        description="Consulte créditos e colete pings brutos do RIPE Atlas.",
    )
    operations = parser.add_subparsers(dest="operation")
    operations.add_parser("getCredits", help="Consultar o saldo de créditos.")
    capture = operations.add_parser(
        "getData",
        help="Criar um ping, imprimir a tabela e acrescentar o histórico em data/raw.",
    )
    capture.add_argument("--target", default=DEFAULT_TARGET)
    capture.add_argument("--af", type=int, default=4, dest="address_family")
    capture.add_argument("--country-code", default="BR")
    capture.add_argument("--probe-count", type=int, default=1)
    capture.add_argument("--packets", type=int, default=16)
    capture.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    if args.operation is None:
        parser.print_help()
        return 0
    api_key = os.environ["RIPE_ATLAS_API_KEY"]
    if args.operation == "getCredits":
        print(f"Créditos: {get_credits(api_key)}")
        return 0
    frame = get_data(
        api_key,
        target=args.target,
        address_family=args.address_family,
        country_code=args.country_code,
        probe_count=args.probe_count,
        packets=args.packets,
    )
    append_data(frame, output_dir=args.output_dir)
    print(frame.to_string(index=False))
    return 0
