"""Controller de terminal: argparse, ambiente e stdout."""

import argparse
import os
from collections.abc import Sequence
from pathlib import Path
from time import sleep, time

from preditor_de_falhas_ml.atlas import (
    DEFAULT_MSM_IDS_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_TARGET,
    HUB_INTERVAL_SECONDS,
    HUB_SPECS,
    append_data,
    create_periodic_measurements,
    fetch_measurement,
    fetch_measurement_results,
    get_credits,
    get_data,
    parse_measurement_ids_csv,
    read_measurement_ids,
    stop_measurement,
    write_measurement_ids,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m preditor_de_falhas_ml",
        description=(
            "Consulte créditos, leia resultados existentes (GET), "
            "crie ou pare as 6 medições periódicas do hub "
            "(POST setup / DELETE stop) ou um ping one-off (POST demo)."
        ),
    )
    operations = parser.add_subparsers(dest="operation")
    operations.add_parser("getCredits", help="Consultar o saldo de créditos.")
    create = operations.add_parser(
        "createPeriodic",
        help=(
            "Criar as 6 medições periódicas do hub (POST; is_oneoff=false, "
            "interval=900). Setup do dataset — não é o collector."
        ),
    )
    create.add_argument(
        "--ids-file",
        type=Path,
        default=None,
        help=(
            f"Gravar os 6 msm_id em JSON (sem a API key). Ex.: {DEFAULT_MSM_IDS_PATH}"
        ),
    )
    create.add_argument(
        "--wait-seconds",
        type=int,
        default=0,
        help=(
            "Esperar N segundos e GET results de cada msm_id "
            f"(um ciclo do hub = {HUB_INTERVAL_SECONDS}). 0 = só o POST."
        ),
    )
    stop = operations.add_parser(
        "stopPeriodic",
        help=(
            "Parar medições periódicas (DELETE /measurements/{id}/). "
            "IDs via --ids-file ou RIPE_ATLAS_MSM_IDS. Não apaga o histórico."
        ),
    )
    stop.add_argument(
        "--ids-file",
        type=Path,
        default=None,
        help=(
            f"JSON com msm_id (sem a API key). Ex.: {DEFAULT_MSM_IDS_PATH}. "
            "Sem arquivo, usa RIPE_ATLAS_MSM_IDS."
        ),
    )
    capture = operations.add_parser(
        "getData",
        help="Criar um ping one-off (POST demo), imprimir a tabela e gravar JSONL.",
    )
    capture.add_argument("--target", default=DEFAULT_TARGET)
    capture.add_argument("--af", type=int, default=4, dest="address_family")
    capture.add_argument("--country-code", default="BR")
    capture.add_argument("--probe-count", type=int, default=1)
    capture.add_argument("--packets", type=int, default=16)
    capture.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    collect = operations.add_parser(
        "getResults",
        help="Ler resultados de uma medição já existente (GET; não cria medição).",
    )
    collect.add_argument("--msm-id", type=int, required=True)
    collect.add_argument("--start", type=int, required=True)
    collect.add_argument("--stop", type=int, required=True)
    collect.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.operation is None:
        parser.print_help()
        return 0
    api_key = os.environ["RIPE_ATLAS_API_KEY"]
    if args.operation == "getCredits":
        print(f"Créditos: {get_credits(api_key)}")
        return 0
    if args.operation == "getResults":
        frame = fetch_measurement_results(
            api_key,
            args.msm_id,
            start=args.start,
            stop=args.stop,
        )
        if args.output_dir is not None:
            append_data(frame, output_dir=args.output_dir)
        print(frame.to_string(index=False))
        return 0
    if args.operation == "createPeriodic":
        credits_before = get_credits(api_key)
        print(f"Créditos antes: {credits_before}")
        msm_ids = create_periodic_measurements(api_key)
        credits_after = get_credits(api_key)
        print(f"Créditos depois: {credits_after}")
        for msm_id, spec in zip(msm_ids, HUB_SPECS, strict=True):
            print(
                f"msm_id={msm_id} target={spec.target} "
                f"type={spec.measurement_type} role={spec.role}"
            )
        print(
            "export RIPE_ATLAS_MSM_IDS=" + ",".join(str(msm_id) for msm_id in msm_ids)
        )
        if args.ids_file is not None:
            written = write_measurement_ids(msm_ids, output_path=args.ids_file)
            print(f"IDs gravados em {written}")
        if args.wait_seconds > 0:
            sleep(args.wait_seconds)
            stop = int(time())
            start = stop - args.wait_seconds
            for msm_id in msm_ids:
                frame = fetch_measurement_results(
                    api_key,
                    msm_id,
                    start=start,
                    stop=stop,
                )
                print(f"GET msm_id={msm_id} linhas={len(frame)}")
                if not frame.empty:
                    print(frame.to_string(index=False))
        return 0
    if args.operation == "stopPeriodic":
        if args.ids_file is not None:
            msm_ids = read_measurement_ids(args.ids_file)
        else:
            env_ids = os.environ.get("RIPE_ATLAS_MSM_IDS", "").strip()
            if not env_ids:
                raise ValueError(
                    "stopPeriodic precisa de --ids-file ou RIPE_ATLAS_MSM_IDS."
                )
            msm_ids = parse_measurement_ids_csv(env_ids)
        credits_before = get_credits(api_key)
        print(f"Créditos antes: {credits_before}")
        for msm_id in msm_ids:
            stop_measurement(api_key, msm_id)
            meta = fetch_measurement(api_key, msm_id)
            status = meta.get("status")
            name = status.get("name") if isinstance(status, dict) else status
            print(f"msm_id={msm_id} status={name}")
        credits_after = get_credits(api_key)
        print(f"Créditos depois: {credits_after}")
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
