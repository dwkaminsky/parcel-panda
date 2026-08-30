from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from pipelines.config import DEFAULT_DATASETS, DatasetId, RunOptions


DEFAULT_OUTPUT_ROOT = Path("pipelines/data/runs")


@dataclass(frozen=True)
class CollectCommand:
    options: RunOptions
    output_root: Path


@dataclass(frozen=True)
class PublishCommand:
    snapshot: Path


PipelineCommand = CollectCommand | PublishCommand


def _add_collection_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dataset",
        action="append",
        choices=tuple(dataset.value for dataset in DatasetId),
        dest="datasets",
        metavar="SLUG",
        help=(
            "dataset to collect; repeat the option to select more than one "
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
        help="retain source payloads in the local snapshot (default: enabled)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        metavar="PATH",
        help="directory under which a timestamped snapshot is created",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipelines",
        description="Collect local property-data snapshots and publish them separately.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser(
        "collect",
        help="fetch and normalize sources into a checksummed local snapshot",
    )
    _add_collection_options(collect)
    publish = commands.add_parser(
        "publish",
        help="verify and publish an existing local snapshot to Postgres",
    )
    publish.add_argument(
        "snapshot",
        type=Path,
        metavar="SNAPSHOT",
        help="snapshot directory or manifest.json path produced by collect",
    )
    return parser


def command_from_args(args: argparse.Namespace) -> PipelineCommand:
    if args.command == "publish":
        return PublishCommand(snapshot=args.snapshot)
    datasets = (
        tuple(DatasetId(dataset) for dataset in args.datasets)
        if args.datasets
        else DEFAULT_DATASETS
    )
    return CollectCommand(
        options=RunOptions(
            datasets=datasets,
            county_fips=args.county_fips,
            dry_run=True,
            limit=args.limit,
            include_raw_payloads=args.raw_payloads,
        ),
        output_root=args.output_root,
    )


def parse_command(argv: Sequence[str] | None = None) -> PipelineCommand:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return command_from_args(args)
    except ValidationError as exc:
        parser.error(str(exc))


def main(argv: Sequence[str] | None = None) -> int:
    command = parse_command(argv)
    if isinstance(command, CollectCommand):
        from pipelines.flow import collect_catalog

        summary = collect_catalog(command.options, command.output_root)
    else:
        from pipelines.flow import publish_catalog

        summary = publish_catalog(command.snapshot)
    print(summary.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
