from __future__ import annotations

from pathlib import Path

import pytest

from pipelines.__main__ import CollectCommand, PublishCommand, parse_command
from pipelines.config import DEFAULT_DATASETS, DatasetId


def test_collect_defaults_are_safe_and_bounded() -> None:
    command = parse_command(["collect"])

    assert isinstance(command, CollectCommand)
    assert command.options.datasets == DEFAULT_DATASETS
    assert command.options.dry_run is True
    assert command.options.limit == 500
    assert command.options.include_raw_payloads is True
    assert command.options.county_fips is None
    assert command.output_root == Path("pipelines/data/runs")


def test_collect_accepts_source_and_local_output_controls() -> None:
    command = parse_command(
        [
            "collect",
            "--dataset",
            "parcel-records",
            "--dataset",
            "housing-demographics",
            "--county-fips",
            "183",
            "--limit",
            "25",
            "--no-raw-payloads",
            "--output-root",
            "/tmp/snapshots",
        ]
    )

    assert isinstance(command, CollectCommand)
    assert command.options.datasets == (
        DatasetId.PARCEL_RECORDS,
        DatasetId.HOUSING_DEMOGRAPHICS,
    )
    assert command.options.county_fips == "37183"
    assert command.options.limit == 25
    assert command.options.include_raw_payloads is False
    assert command.output_root == Path("/tmp/snapshots")


def test_publish_accepts_snapshot_directory() -> None:
    command = parse_command(["publish", "/tmp/snapshots/run-1"])

    assert command == PublishCommand(snapshot=Path("/tmp/snapshots/run-1"))


def test_write_flag_is_not_available_to_collection() -> None:
    with pytest.raises(SystemExit) as raised:
        parse_command(["collect", "--write"])

    assert raised.value.code == 2


def test_command_is_required() -> None:
    with pytest.raises(SystemExit) as raised:
        parse_command([])

    assert raised.value.code == 2


def test_limit_must_stay_within_run_options_bounds() -> None:
    with pytest.raises(SystemExit) as raised:
        parse_command(["collect", "--limit", "5001"])

    assert raised.value.code == 2
