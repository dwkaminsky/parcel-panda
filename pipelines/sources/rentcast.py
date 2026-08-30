from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Literal

from pipelines.config import RunOptions
from pipelines.contracts import ExtractedBatch, NormalizedRecord, RecordKind, canonical_hash
from pipelines.sources.arcgis import HTTP_TIMEOUT, HTTPSession, SourceResponseError, new_session
from pipelines.sources.utils import (
    as_float,
    as_int,
    clean_text,
    nc_county_fips,
    parse_datetime,
)


SALE_URL = "https://api.rentcast.io/v1/listings/sale"
RENTAL_URL = "https://api.rentcast.io/v1/listings/rental/long-term"
PAGE_SIZE = 500


def normalize_rentcast_listing(
    listing: dict[str, Any],
    *,
    listing_type: Literal["sale", "rental"],
    retrieved_at: datetime,
    include_raw_payload: bool = True,
) -> NormalizedRecord | None:
    """Normalize one RentCast listing without doing I/O."""
    source_listing_id = clean_text(listing.get("id"))
    state = clean_text(listing.get("state"))
    if not source_listing_id or not state or state.upper() != "NC":
        return None
    county_fips = nc_county_fips(
        listing.get("stateFips") or "37", listing.get("countyFips")
    )
    listed_at = parse_datetime(listing.get("listedDate"))
    last_seen_at = parse_datetime(listing.get("lastSeenDate"))

    return NormalizedRecord(
        kind=RecordKind.LISTING,
        source_key=source_listing_id,
        data={
            "listing_type": listing_type,
            "source_listing_id": source_listing_id,
            "status": clean_text(listing.get("status")) or "Unknown",
            "address": clean_text(listing.get("formattedAddress")),
            "city": clean_text(listing.get("city")),
            "state": "NC",
            "zip_code": (clean_text(listing.get("zipCode")) or "")[:10] or None,
            "county_fips": county_fips,
            "latitude": as_float(listing.get("latitude")),
            "longitude": as_float(listing.get("longitude")),
            "asking_price": as_float(listing.get("price")),
            "bedrooms": as_float(listing.get("bedrooms")),
            "bathrooms": as_float(listing.get("bathrooms")),
            "square_feet": as_int(listing.get("squareFootage")),
            "property_type": clean_text(listing.get("propertyType")),
            "listed_at": listed_at,
            "last_seen_at": last_seen_at,
            "updated_at": last_seen_at or retrieved_at,
        },
        raw_payload=listing if include_raw_payload else {},
        source_modified_at=last_seen_at,
        content_hash=canonical_hash(listing),
    )


def fetch_rentcast_listings(
    session: HTTPSession,
    url: str,
    *,
    api_key: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Fetch state-filtered RentCast listings in pages of at most 500."""
    listings: list[dict[str, Any]] = []
    offset = 0
    while len(listings) < limit:
        requested = min(PAGE_SIZE, limit - len(listings))
        response = session.get(
            url,
            params={
                "state": "NC",
                "status": "Active",
                "limit": requested,
                "offset": offset,
            },
            headers={"X-Api-Key": api_key},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise SourceResponseError("RentCast response was not a listings array")
        page = [listing for listing in payload if isinstance(listing, dict)]
        listings.extend(page[: limit - len(listings)])
        if len(payload) < requested:
            break
        offset += len(payload)
    return listings


class RentCastListingsAdapter:
    listing_type: Literal["sale", "rental"]
    endpoint_url: str
    credential_env_var = "RENTCAST_API_KEY"

    def __init__(self, session: HTTPSession | None = None) -> None:
        self.session = session or new_session()

    def extract(self, options: RunOptions) -> ExtractedBatch:
        retrieved_at = datetime.now(timezone.utc)
        api_key = os.getenv(self.credential_env_var, "").strip()
        if not api_key:
            return ExtractedBatch(
                dataset_slug=self.dataset_slug,
                source_slug=self.source_slug,
                retrieved_at=retrieved_at,
                skipped_reason=f"{self.credential_env_var} is not configured",
            )

        listings = fetch_rentcast_listings(
            self.session,
            self.endpoint_url,
            api_key=api_key,
            limit=options.limit,
        )
        records: list[NormalizedRecord] = []
        for listing in listings:
            record = normalize_rentcast_listing(
                listing,
                listing_type=self.listing_type,
                retrieved_at=retrieved_at,
                include_raw_payload=options.include_raw_payloads,
            )
            if record is None:
                continue
            if options.county_fips and record.data["county_fips"] != options.county_fips:
                continue
            records.append(record)

        warnings = []
        if len(listings) != len(records):
            warnings.append(
                f"Skipped {len(listings) - len(records)} listing(s) outside "
                "the requested NC geography or without an ID"
            )
        return ExtractedBatch(
            dataset_slug=self.dataset_slug,
            source_slug=self.source_slug,
            retrieved_at=retrieved_at,
            records=records,
            warnings=warnings,
        )


class RentCastSaleAdapter(RentCastListingsAdapter):
    dataset_slug = "active-sale-listings"
    source_slug = "rentcast-sale"
    listing_type: Literal["sale"] = "sale"
    endpoint_url = SALE_URL


class RentCastRentalAdapter(RentCastListingsAdapter):
    dataset_slug = "active-rental-listings"
    source_slug = "rentcast-rental"
    listing_type: Literal["rental"] = "rental"
    endpoint_url = RENTAL_URL
