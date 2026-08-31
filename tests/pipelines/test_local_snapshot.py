from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipelines.config import DatasetId, RunOptions
from pipelines.contracts import ExtractedBatch, NormalizedRecord, RecordKind
from pipelines.local_snapshot import load_snapshot, save_snapshot


def sample_batch() -> ExtractedBatch:
    return ExtractedBatch(
        dataset_slug="parcel-records",
        source_slug="nc-onemap-parcels",
        source_version="fixture-v1",
        retrieved_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
        records=[
            NormalizedRecord(
                kind=RecordKind.PROPERTY,
                source_key="37183:sample-1",
                data={
                    "county_fips": "37183",
                    "parcel_id": "sample-1",
                    "address": "1 Test Way",
                },
                raw_payload={"PARCEL": "sample-1"},
            )
        ],
        warnings=["fixture warning"],
    )


def test_snapshot_round_trip_is_complete_and_publishable(tmp_path: Path) -> None:
    options = RunOptions(
        datasets=(DatasetId.PARCEL_RECORDS,),
        county_fips="37183",
        limit=1,
    )

    summary = save_snapshot([sample_batch()], options, tmp_path)
    loaded = load_snapshot(summary.snapshot_path)

    assert summary.extracted == 1
    assert summary.snapshot_path.parent == tmp_path.resolve()
    assert summary.manifest_path.exists()
    assert loaded.manifest.options["dry_run"] is True
    assert loaded.manifest.batches[0].record_count == 1
    assert loaded.batches == [sample_batch()]


def test_snapshot_can_be_loaded_from_manifest_path(tmp_path: Path) -> None:
    summary = save_snapshot([sample_batch()], RunOptions(limit=1), tmp_path)

    loaded = load_snapshot(summary.manifest_path)

    assert loaded.manifest.snapshot_id == summary.snapshot_path.name


def test_snapshot_detects_tampered_data_before_publish(tmp_path: Path) -> None:
    summary = save_snapshot([sample_batch()], RunOptions(limit=1), tmp_path)
    data_path = next(summary.snapshot_path.glob("*.jsonl.gz"))
    data_path.write_bytes(data_path.read_bytes() + b"tampered")

    with pytest.raises(ValueError, match="Checksum mismatch"):
        load_snapshot(summary.snapshot_path)


def test_snapshot_rejects_manifest_path_traversal(tmp_path: Path) -> None:
    summary = save_snapshot([sample_batch()], RunOptions(limit=1), tmp_path)
    manifest = summary.manifest_path.read_text(encoding="utf-8")
    summary.manifest_path.write_text(
        manifest.replace('"file": "01-', '"file": "../01-'),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="escapes its directory"):
        load_snapshot(summary.snapshot_path)
