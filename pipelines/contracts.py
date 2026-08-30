from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RecordKind(StrEnum):
    PROPERTY = "property"
    INDICATOR = "indicator"
    LISTING = "listing"
    SPATIAL = "spatial"


def canonical_hash(payload: dict[str, Any] | list[Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class NormalizedRecord(BaseModel):
    kind: RecordKind
    source_key: str
    data: dict[str, Any]
    raw_payload: dict[str, Any] | list[Any]
    source_modified_at: datetime | None = None
    content_hash: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash:
            hash_input = self.raw_payload if self.raw_payload else self.data
            self.content_hash = canonical_hash(hash_input)


class ExtractedBatch(BaseModel):
    dataset_slug: str
    source_slug: str
    source_version: str | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    records: list[NormalizedRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    skipped_reason: str | None = None


class LoadSummary(BaseModel):
    dataset_slug: str
    source_slug: str
    extracted: int
    loaded: int = 0
    unchanged: int = 0
    errors: int = 0
    dry_run: bool
    skipped_reason: str | None = None


class CatalogRunSummary(BaseModel):
    datasets_requested: int
    batches: list[LoadSummary]
    dry_run: bool

    @property
    def loaded(self) -> int:
        return sum(batch.loaded for batch in self.batches)

    @property
    def extracted(self) -> int:
        return sum(batch.extracted for batch in self.batches)


class SnapshotBatch(BaseModel):
    dataset_slug: str
    source_slug: str
    source_version: str | None = None
    retrieved_at: datetime
    record_count: int = Field(ge=0)
    file: str
    sha256: str
    warnings: list[str] = Field(default_factory=list)
    skipped_reason: str | None = None


class SnapshotManifest(BaseModel):
    schema_version: int = 1
    snapshot_id: str
    created_at: datetime
    options: dict[str, Any]
    batches: list[SnapshotBatch]


class LocalCollectionSummary(BaseModel):
    snapshot_path: Path
    manifest_path: Path
    batches: list[LoadSummary]

    @property
    def extracted(self) -> int:
        return sum(batch.extracted for batch in self.batches)


class LoadedSnapshot(BaseModel):
    manifest: SnapshotManifest
    batches: list[ExtractedBatch]
