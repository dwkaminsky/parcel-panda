from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pipelines.config import RunOptions
from pipelines.contracts import ExtractedBatch, NormalizedRecord, RecordKind, canonical_hash
from pipelines.sources.arcgis import HTTPSession, fetch_arcgis_features, new_session
from pipelines.sources.utils import as_float, clean_text, nc_county_fips, parse_datetime


LAYER_URL = (
    "https://services.nconemap.gov/secure/rest/services/"
    "NC1Map_Parcels/FeatureServer/0"
)
POLYGON_LAYER_URL = (
    "https://services.nconemap.gov/secure/rest/services/"
    "NC1Map_Parcels/FeatureServer/1"
)


def normalize_nc_onemap_parcel(
    feature: dict[str, Any],
    *,
    retrieved_at: datetime,
    include_raw_payload: bool = True,
) -> NormalizedRecord | None:
    """Normalize one NC OneMap parcel-point feature without doing I/O."""
    attributes = feature.get("attributes")
    if not isinstance(attributes, dict):
        return None

    county_fips = nc_county_fips(
        attributes.get("stfips"),
        attributes.get("stcntyfips") or attributes.get("cntyfips"),
    )
    parcel_id = clean_text(attributes.get("parno") or attributes.get("nparno"))
    if not county_fips or not parcel_id:
        return None

    geometry = feature.get("geometry")
    geometry = geometry if isinstance(geometry, dict) else None
    source_modified_at = (
        parse_datetime(attributes.get("revisedate"))
        or parse_datetime(attributes.get("transfdate"))
        or parse_datetime(attributes.get("sourcedate"))
    )
    updated_at = source_modified_at or retrieved_at

    return NormalizedRecord(
        kind=RecordKind.PROPERTY,
        source_key=f"{county_fips}:{parcel_id}",
        data={
            "county_fips": county_fips,
            "parcel_id": parcel_id,
            "owner_name": clean_text(attributes.get("ownname")),
            "address": clean_text(attributes.get("siteadd")),
            "city": clean_text(attributes.get("scity")),
            "state": "NC",
            "zip_code": (clean_text(attributes.get("szip")) or "")[:10] or None,
            "acreage": as_float(attributes.get("gisacres")),
            "land_value": as_float(attributes.get("landval")),
            "building_value": as_float(attributes.get("improvval")),
            "assessed_value": as_float(attributes.get("parval")),
            "latitude": as_float(geometry.get("y")) if geometry else None,
            "longitude": as_float(geometry.get("x")) if geometry else None,
            "geometry": geometry,
            "updated_at": updated_at,
        },
        raw_payload=feature if include_raw_payload else {},
        source_modified_at=source_modified_at,
        content_hash=canonical_hash(feature),
    )


class NCOneMapParcelAdapter:
    dataset_slug = "parcel-records"
    source_slug = "nc-onemap-parcels"
    layer_url = LAYER_URL

    def __init__(self, session: HTTPSession | None = None) -> None:
        self.session = session or new_session()

    def extract(self, options: RunOptions) -> ExtractedBatch:
        retrieved_at = datetime.now(timezone.utc)
        where = "stfips = '37'"
        if options.county_fips:
            where = f"stcntyfips = '{options.county_fips}'"
        features = fetch_arcgis_features(
            self.session,
            self.layer_url,
            where=where,
            limit=options.limit,
            page_size=5_000,
            order_by="objectid ASC",
        )

        records = [
            record
            for feature in features
            if (
                record := normalize_nc_onemap_parcel(
                    feature,
                    retrieved_at=retrieved_at,
                    include_raw_payload=options.include_raw_payloads,
                )
            )
        ]
        warnings = []
        invalid_count = len(features) - len(records)
        if invalid_count:
            warnings.append(
                f"Skipped {invalid_count} parcel feature(s) without a valid "
                "NC county FIPS or parcel ID"
            )
        return ExtractedBatch(
            dataset_slug=self.dataset_slug,
            source_slug=self.source_slug,
            retrieved_at=retrieved_at,
            records=records,
            warnings=warnings,
        )


# Backwards-friendly plural spelling for registry code.
NCOneMapParcelsAdapter = NCOneMapParcelAdapter


class NCOneMapAssessedValueAdapter(NCOneMapParcelAdapter):
    """Expose the same parcel observations through the assessed-value dataset."""

    dataset_slug = "property-tax"


class NCOneMapOwnershipAdapter(NCOneMapParcelAdapter):
    """Load county ownership attributes with the parcel polygon when available."""

    dataset_slug = "ownership-boundaries"
    layer_url = POLYGON_LAYER_URL
