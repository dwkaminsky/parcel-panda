from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pipelines.config import RunOptions
from pipelines.contracts import ExtractedBatch, NormalizedRecord, RecordKind, canonical_hash
from pipelines.sources.arcgis import HTTPSession, fetch_arcgis_features, new_session
from pipelines.sources.utils import clean_text


LAYER_URL = (
    "https://spartagis.ncem.org/arcgis/rest/services/Public/"
    "FRIS_FloodZones/MapServer/2"
)
ZONE_NAMES = {
    "1000": "Zone A",
    "1001": "Zone AE",
    "1002": "Zone AH",
    "1003": "Zone AO",
    "1007": "Zone A99",
    "1008": "Zone V",
    "1009": "Zone VE",
    "2000": "0.2% annual chance flood hazard",
    "2001": "0.2% annual chance flood hazard contained in channel",
    "3000": "Area not included",
    "3002": "1% future conditions contained in channel",
    "4000": "Zone D",
    "4002": "Zone X",
    "5000": "Open water",
}


def normalize_ncem_flood_feature(
    feature: dict[str, Any],
    *,
    retrieved_at: datetime,
    include_raw_payload: bool = True,
) -> NormalizedRecord | None:
    """Normalize a FRIS flood-hazard polygon without doing I/O."""
    attributes = feature.get("attributes")
    if not isinstance(attributes, dict):
        return None
    source_feature_id = clean_text(attributes.get("V_FLDARID") or attributes.get("OBJECTID"))
    if not source_feature_id:
        return None

    state_fips = clean_text(attributes.get("ST_FIPS"))
    county_code = clean_text(attributes.get("CO_FIPS"))
    if state_fips != "37":
        return None
    geometry = feature.get("geometry")
    geometry = geometry if isinstance(geometry, dict) else None
    zone_code = clean_text(attributes.get("ZONE_LID"))
    zone_name = clean_text(attributes.get("ZONE_LID_VALUE")) or ZONE_NAMES.get(
        zone_code or ""
    )
    properties = dict(attributes)
    if county_code and county_code.isdigit():
        properties["county_fips"] = f"37{county_code.zfill(3)}"

    return NormalizedRecord(
        kind=RecordKind.SPATIAL,
        source_key=source_feature_id,
        data={
            "dataset_slug": "flood-hazards",
            "source_layer": "Flood Hazard Areas",
            "source_feature_id": source_feature_id,
            "feature_type": "flood_hazard_area",
            "name": zone_name,
            "jurisdiction": "North Carolina",
            "geometry": geometry,
            "properties": properties,
            "updated_at": retrieved_at,
        },
        raw_payload=feature if include_raw_payload else {},
        content_hash=canonical_hash(feature),
    )


class NCEMFloodAdapter:
    dataset_slug = "flood-hazards"
    source_slug = "ncem-fris"

    def __init__(self, session: HTTPSession | None = None) -> None:
        self.session = session or new_session()

    def extract(self, options: RunOptions) -> ExtractedBatch:
        retrieved_at = datetime.now(timezone.utc)
        where = "ST_FIPS = '37'"
        if options.county_fips:
            where += f" AND CO_FIPS = '{options.county_fips[2:]}'"
        features = fetch_arcgis_features(
            self.session,
            LAYER_URL,
            where=where,
            limit=options.limit,
            page_size=3_000,
            order_by="OBJECTID ASC",
        )
        records = [
            record
            for feature in features
            if (
                record := normalize_ncem_flood_feature(
                    feature,
                    retrieved_at=retrieved_at,
                    include_raw_payload=options.include_raw_payloads,
                )
            )
        ]
        warnings = []
        if len(features) != len(records):
            warnings.append(
                f"Skipped {len(features) - len(records)} flood feature(s) "
                "without a stable ID or NC geography"
            )
        return ExtractedBatch(
            dataset_slug=self.dataset_slug,
            source_slug=self.source_slug,
            retrieved_at=retrieved_at,
            records=records,
            warnings=warnings,
        )


NCEMFrisAdapter = NCEMFloodAdapter
