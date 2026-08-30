from __future__ import annotations

import argparse
from collections.abc import Sequence

from pydantic import ValidationError

from pipelines.config import DEFAULT_DATASETS, DatasetId, RunOptions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipelines",
        description="Run Parcel Panda's Prefect data catalog pipeline.",
    )
    parser.add_argument(
        "--dataset",
        action="append",
        choices=tuple(dataset.value for dataset in DatasetId),
        dest="datasets",
        metavar="SLUG",
        help=(
            "dataset to run; repeat the option to select more than one "
            "(defaults to the public catalog starter set)"
        ),
    )
    parser.add_argument(
        "--county-fips",
        metavar="FIPS",
        help="North Carolina county FIPS (for example, 183 or 37183 for Wake County)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=RunOptions.model_fields["limit"].default,
        metavar="N",
        help="maximum records requested from each source (default: %(default)s; max: 5000)",
    )
    parser.add_argument(
        "--raw-payloads",
        action=argparse.BooleanOptionalAction,
        default=RunOptions.model_fields["include_raw_payloads"].default,
        help="retain source payloads for provenance and debugging (default: enabled)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write normalized records to the database (the default is a safe dry run)",
    )
    return parser


def options_from_args(args: argparse.Namespace) -> RunOptions:
    datasets = (
        tuple(DatasetId(dataset) for dataset in args.datasets)
        if args.datasets
        else DEFAULT_DATASETS
    )
    return RunOptions(
        datasets=datasets,
        county_fips=args.county_fips,
        dry_run=not args.write,
        limit=args.limit,
        include_raw_payloads=args.raw_payloads,
    )


def parse_options(argv: Sequence[str] | None = None) -> RunOptions:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return options_from_args(args)
    except ValidationError as exc:
        parser.error(str(exc))


def main(argv: Sequence[str] | None = None) -> int:
    options = parse_options(argv)

    # Importing lazily keeps parser and help usage independent of Prefect startup.
    from pipelines.flow import run_catalog

    summary = run_catalog(options)
    print(summary.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
