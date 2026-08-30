from __future__ import annotations

from typing import Protocol

from pipelines.config import RunOptions
from pipelines.contracts import ExtractedBatch


class SourceAdapter(Protocol):
    dataset_slug: str
    source_slug: str

    def extract(self, options: RunOptions) -> ExtractedBatch: ...
