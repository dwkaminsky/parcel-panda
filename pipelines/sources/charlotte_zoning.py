from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pipelines.config import RunOptions
from pipelines.contracts import ExtractedBatch, NormalizedRecord, RecordKind, canonical_hash
from pipelines.sources.arcgis import HTTPSession, fetch_arcgis_features, new_session
from pipelines.sources.utils import clean_text, parse_datetime


LAYER_URL = "https://gis.charlottenc.gov/arcgis/rest/services/PLN/Zoning/MapServer/0"
MECKLENBURG_COUNTY_FIPS = "37119"


def normalize_charlotte_zoning_feature(
    feature: dict[str, Any],
    *,
    retrieved_at: datetime,
    include_raw_payload: bool = True,
) -> NormalizedRecord | None:
    """Normalize a Charlotte zoning polygon without doing I/O."""
    attributes = feature.get("attributes")
    if not isinstance(attributes, dict):
        return None
    source_feature_id = clean_text(attributes.get("OBJECTID"))
    if not source_feature_id:
        return None
    geometry = feature.get("geometry")
    geometry = geometry if isinstance(geometry, dict) else None
    source_modified_at = parse_datetime(attributes.get("RezoneDate"))

    return NormalizedRecord(
        kind=RecordKind.SPATIAL,
        source_key=source_feature_id,
        data={
            "dataset_slug": "zoning-land-use",
            "source_layer": "Zoning",
            "source_feature_id": source_feature_id,
            "feature_type": "zoning_district",
            "name": clean_text(attributes.get("ZoneDes")),
            "jurisdiction": "Charlotte, NC",
            "geometry": geometry,
            "properties": dict(attributes),
            "updated_at": source_modified_at or retrieved_at,
        },
        raw_payload=feature if include_raw_payload else {},
        source_modified_at=source_modified_at,
        content_hash=canonical_hash(feature),
    )


class CharlotteZoningAdapter:
    dataset_slug = "zoning-land-use"
    source_slug = "charlotte-zoning"

    def __init__(self, session: HTTPSession | None = None) -> None:
        self.session = session or new_session()

    def extract(self, options: RunOptions) -> ExtractedBatch:
        retrieved_at = datetime.now(timezone.utc)
        if options.county_fips and options.county_fips != MECKLENBURG_COUNTY_FIPS:
            return ExtractedBatch(
                dataset_slug=self.dataset_slug,
                source_slug=self.source_slug,
                retrieved_at=retrieved_at,
                skipped_reason="Charlotte zoning is only available for Mecklenburg County (37119)",
            )

        features = fetch_arcgis_features(
            self.session,
            LAYER_URL,
            where="1 = 1",
            limit=options.limit,
            page_size=2_000,
            order_by="OBJECTID ASC",
        )
        records = [
            record
            for feature in features
            if (
                record := normalize_charlotte_zoning_feature(
                    feature,
                    retrieved_at=retrieved_at,
                    include_raw_payload=options.include_raw_payloads,
                )
            )
        ]
        warnings = []
        if len(features) != len(records):
            warnings.append(
                f"Skipped {len(features) - len(records)} zoning feature(s) without an OBJECTID"
            )
        return ExtractedBatch(
            dataset_slug=self.dataset_slug,
            source_slug=self.source_slug,
            retrieved_at=retrieved_at,
            records=records,
            warnings=warnings,
        )
