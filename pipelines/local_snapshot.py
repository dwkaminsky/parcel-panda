from __future__ import annotations

import gzip
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pipelines.config import RunOptions
from pipelines.contracts import (
    ExtractedBatch,
    LoadedSnapshot,
    LocalCollectionSummary,
    LoadSummary,
    NormalizedRecord,
    SnapshotBatch,
    SnapshotManifest,
)


MANIFEST_FILENAME = "manifest.json"
SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _batch_filename(batch: ExtractedBatch, position: int) -> str:
    dataset = SAFE_NAME.sub("-", batch.dataset_slug).strip("-")
    source = SAFE_NAME.sub("-", batch.source_slug).strip("-")
    return f"{position:02d}-{dataset}__{source}.jsonl.gz"


def save_snapshot(
    batches: list[ExtractedBatch],
    options: RunOptions,
    output_root: str | Path,
) -> LocalCollectionSummary:
    """Atomically save normalized batches and a checksummed manifest locally."""
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc)
    snapshot_id = f"{created_at:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    temporary = root / f".{snapshot_id}.tmp"
    destination = root / snapshot_id
    temporary.mkdir()

    references: list[SnapshotBatch] = []
    summaries: list[LoadSummary] = []
    try:
        for position, batch in enumerate(batches, start=1):
            filename = _batch_filename(batch, position)
            data_path = temporary / filename
            with gzip.open(data_path, "wt", encoding="utf-8", newline="\n") as output:
                for record in batch.records:
                    output.write(record.model_dump_json())
                    output.write("\n")
            references.append(
                SnapshotBatch(
                    dataset_slug=batch.dataset_slug,
                    source_slug=batch.source_slug,
                    source_version=batch.source_version,
                    retrieved_at=batch.retrieved_at,
                    record_count=len(batch.records),
                    file=filename,
                    sha256=_sha256(data_path),
                    warnings=batch.warnings,
                    skipped_reason=batch.skipped_reason,
                )
            )
            summaries.append(
                LoadSummary(
                    dataset_slug=batch.dataset_slug,
                    source_slug=batch.source_slug,
                    extracted=len(batch.records),
                    dry_run=True,
                    skipped_reason=batch.skipped_reason,
                )
            )

        manifest = SnapshotManifest(
            snapshot_id=snapshot_id,
            created_at=created_at,
            options=options.model_dump(mode="json"),
            batches=references,
        )
        manifest_path = temporary / MANIFEST_FILENAME
        manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    except Exception:
        for path in temporary.iterdir() if temporary.exists() else ():
            path.unlink()
        if temporary.exists():
            temporary.rmdir()
        raise

    return LocalCollectionSummary(
        snapshot_path=destination,
        manifest_path=destination / MANIFEST_FILENAME,
        batches=summaries,
    )


def _manifest_path(snapshot: str | Path) -> Path:
    path = Path(snapshot).expanduser().resolve()
    return path / MANIFEST_FILENAME if path.is_dir() else path


def load_snapshot(snapshot: str | Path) -> LoadedSnapshot:
    """Validate a complete local snapshot before any publishing begins."""
    manifest_path = _manifest_path(snapshot)
    manifest = SnapshotManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    if manifest.schema_version != 1:
        raise ValueError(f"Unsupported snapshot schema version: {manifest.schema_version}")

    snapshot_root = manifest_path.parent.resolve()
    batches: list[ExtractedBatch] = []
    for reference in manifest.batches:
        data_path = (snapshot_root / reference.file).resolve()
        if snapshot_root not in data_path.parents:
            raise ValueError(f"Snapshot file escapes its directory: {reference.file}")
        actual_hash = _sha256(data_path)
        if actual_hash != reference.sha256:
            raise ValueError(f"Checksum mismatch for snapshot file: {reference.file}")

        records: list[NormalizedRecord] = []
        with gzip.open(data_path, "rt", encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if line.strip():
                    try:
                        records.append(NormalizedRecord.model_validate_json(line))
                    except ValueError as exc:
                        raise ValueError(
                            f"Invalid record in {reference.file} at line {line_number}"
                        ) from exc
        if len(records) != reference.record_count:
            raise ValueError(
                f"Record count mismatch for {reference.file}: "
                f"expected {reference.record_count}, found {len(records)}"
            )
        batches.append(
            ExtractedBatch(
                dataset_slug=reference.dataset_slug,
                source_slug=reference.source_slug,
                source_version=reference.source_version,
                retrieved_at=reference.retrieved_at,
                records=records,
                warnings=reference.warnings,
                skipped_reason=reference.skipped_reason,
            )
        )
    return LoadedSnapshot(manifest=manifest, batches=batches)
