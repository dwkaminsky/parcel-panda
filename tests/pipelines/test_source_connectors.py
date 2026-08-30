from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from pipelines.config import DatasetId, RunOptions
from pipelines.contracts import RecordKind
from pipelines.sources.arcgis import SourceResponseError, fetch_arcgis_features
from pipelines.sources.charlotte_zoning import (
    CharlotteZoningAdapter,
    normalize_charlotte_zoning_feature,
)
from pipelines.sources.nc_onemap import (
    NCOneMapAssessedValueAdapter,
    NCOneMapParcelAdapter,
    normalize_nc_onemap_parcel,
)
from pipelines.sources.ncem_fris import NCEMFloodAdapter, normalize_ncem_flood_feature
from pipelines.sources.rentcast import (
    RentCastRentalAdapter,
    RentCastSaleAdapter,
    fetch_rentcast_listings,
    normalize_rentcast_listing,
)


FIXTURES = Path(__file__).parent / "fixtures"
RETRIEVED_AT = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)


def load_fixture(name: str) -> dict:
    with (FIXTURES / name).open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


class FakeResponse:
    def __init__(self, payload, *, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads) -> None:
        self.payloads = list(payloads)
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payloads.pop(0))


class NormalizerTests(unittest.TestCase):
    def test_normalizes_nc_onemap_parcel_and_assessed_values(self) -> None:
        feature = load_fixture("nc_onemap_parcel.json")

        record = normalize_nc_onemap_parcel(feature, retrieved_at=RETRIEVED_AT)

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.kind, RecordKind.PROPERTY)
        self.assertEqual(record.source_key, "37183:012345")
        self.assertEqual(record.data["county_fips"], "37183")
        self.assertEqual(record.data["assessed_value"], 475000.0)
        self.assertEqual(record.data["land_value"], 125000.0)
        self.assertEqual(record.data["building_value"], 350000.0)
        self.assertEqual(record.data["latitude"], 35.7796)
        self.assertEqual(record.source_modified_at.isoformat(), "2025-01-01T00:00:00+00:00")

    def test_rejects_non_nc_or_incomplete_parcels(self) -> None:
        feature = load_fixture("nc_onemap_parcel.json")
        feature["attributes"]["stcntyfips"] = "45183"
        feature["attributes"]["stfips"] = "45"

        self.assertIsNone(normalize_nc_onemap_parcel(feature, retrieved_at=RETRIEVED_AT))

    def test_normalizes_ncem_flood_feature(self) -> None:
        feature = load_fixture("ncem_flood_feature.json")

        record = normalize_ncem_flood_feature(feature, retrieved_at=RETRIEVED_AT)

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.kind, RecordKind.SPATIAL)
        self.assertEqual(record.data["dataset_slug"], "flood-hazards")
        self.assertEqual(record.data["feature_type"], "flood_hazard_area")
        self.assertEqual(record.data["name"], "AE")
        self.assertEqual(record.data["properties"]["county_fips"], "37183")
        self.assertIn("rings", record.data["geometry"])

    def test_normalizes_charlotte_zoning_feature(self) -> None:
        feature = load_fixture("charlotte_zoning_feature.json")

        record = normalize_charlotte_zoning_feature(feature, retrieved_at=RETRIEVED_AT)

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.kind, RecordKind.SPATIAL)
        self.assertEqual(record.source_key, "303")
        self.assertEqual(record.data["name"], "N1-B")
        self.assertEqual(record.data["jurisdiction"], "Charlotte, NC")
        self.assertEqual(record.source_modified_at.isoformat(), "2024-04-01T00:00:00+00:00")

    def test_normalizes_sale_and_rental_listings(self) -> None:
        listing = load_fixture("rentcast_listing.json")

        sale = normalize_rentcast_listing(
            listing, listing_type="sale", retrieved_at=RETRIEVED_AT
        )
        rental = normalize_rentcast_listing(
            listing, listing_type="rental", retrieved_at=RETRIEVED_AT
        )

        self.assertIsNotNone(sale)
        self.assertIsNotNone(rental)
        assert sale is not None and rental is not None
        self.assertEqual(sale.kind, RecordKind.LISTING)
        self.assertEqual(sale.data["listing_type"], "sale")
        self.assertEqual(rental.data["listing_type"], "rental")
        self.assertEqual(sale.data["county_fips"], "37183")
        self.assertEqual(sale.data["asking_price"], 525000.0)
        self.assertEqual(sale.data["bathrooms"], 2.5)
        self.assertEqual(sale.data["last_seen_at"].isoformat(), "2026-08-29T12:30:00+00:00")

    def test_can_omit_raw_payload(self) -> None:
        listing = load_fixture("rentcast_listing.json")
        record = normalize_rentcast_listing(
            listing,
            listing_type="sale",
            retrieved_at=RETRIEVED_AT,
            include_raw_payload=False,
        )
        listing["price"] += 1
        changed_record = normalize_rentcast_listing(
            listing,
            listing_type="sale",
            retrieved_at=RETRIEVED_AT,
            include_raw_payload=False,
        )

        assert record is not None and changed_record is not None
        self.assertEqual(record.raw_payload, {})
        self.assertNotEqual(record.content_hash, changed_record.content_hash)


class ExtractionTests(unittest.TestCase):
    def test_arcgis_pagination_is_bounded_and_uses_timeout(self) -> None:
        session = FakeSession(
            [
                {"features": [{"attributes": {"OBJECTID": 1}}], "exceededTransferLimit": True},
                {"features": [{"attributes": {"OBJECTID": 2}}], "exceededTransferLimit": False},
            ]
        )

        features = fetch_arcgis_features(
            session,
            "https://example.test/FeatureServer/0",
            where="ST_FIPS = '37'",
            limit=2,
            page_size=1,
            order_by="OBJECTID ASC",
        )

        self.assertEqual(len(features), 2)
        self.assertEqual(len(session.calls), 2)
        first_params = session.calls[0][1]["params"]
        second_params = session.calls[1][1]["params"]
        self.assertEqual(first_params["resultOffset"], 0)
        self.assertEqual(second_params["resultOffset"], 1)
        self.assertEqual(first_params["outSR"], 4326)
        self.assertEqual(session.calls[0][1]["timeout"], (5, 45))

    def test_arcgis_error_payload_is_not_silently_accepted(self) -> None:
        session = FakeSession([{"error": {"message": "Invalid query"}}])

        with self.assertRaisesRegex(SourceResponseError, "Invalid query"):
            fetch_arcgis_features(
                session,
                "https://example.test/FeatureServer/0",
                where="1 = 1",
                limit=1,
                page_size=1,
                order_by="OBJECTID ASC",
            )

    def test_onemap_adapter_applies_county_filter(self) -> None:
        feature = load_fixture("nc_onemap_parcel.json")
        session = FakeSession([{"features": [feature], "exceededTransferLimit": False}])
        adapter = NCOneMapParcelAdapter(session=session)

        batch = adapter.extract(
            RunOptions(
                datasets=(DatasetId.PARCEL_RECORDS,),
                county_fips="37183",
                limit=1,
            )
        )

        self.assertEqual(len(batch.records), 1)
        self.assertEqual(
            session.calls[0][1]["params"]["where"], "stcntyfips = '37183'"
        )

    def test_onemap_assessed_value_adapter_routes_to_property_tax_dataset(self) -> None:
        feature = load_fixture("nc_onemap_parcel.json")
        session = FakeSession([{"features": [feature], "exceededTransferLimit": False}])

        batch = NCOneMapAssessedValueAdapter(session=session).extract(
            RunOptions(datasets=(DatasetId.PROPERTY_TAX,), limit=1)
        )

        self.assertEqual(batch.dataset_slug, "property-tax")
        self.assertEqual(batch.source_slug, "nc-onemap-parcels")
        self.assertEqual(batch.records[0].data["assessed_value"], 475000.0)

    def test_charlotte_adapter_skips_other_counties_without_http(self) -> None:
        session = FakeSession([])
        adapter = CharlotteZoningAdapter(session=session)

        batch = adapter.extract(
            RunOptions(datasets=(DatasetId.ZONING,), county_fips="37183", limit=1)
        )

        self.assertIn("Mecklenburg", batch.skipped_reason or "")
        self.assertEqual(session.calls, [])

    def test_ncem_adapter_applies_nc_county_filter(self) -> None:
        feature = load_fixture("ncem_flood_feature.json")
        session = FakeSession([{"features": [feature], "exceededTransferLimit": False}])

        batch = NCEMFloodAdapter(session=session).extract(
            RunOptions(datasets=(DatasetId.FLOOD_HAZARDS,), county_fips="37183", limit=1)
        )

        self.assertEqual(len(batch.records), 1)
        self.assertEqual(
            session.calls[0][1]["params"]["where"],
            "ST_FIPS = '37' AND CO_FIPS = '183'",
        )

    def test_charlotte_adapter_extracts_mecklenburg_zoning(self) -> None:
        feature = load_fixture("charlotte_zoning_feature.json")
        session = FakeSession([{"features": [feature], "exceededTransferLimit": False}])

        batch = CharlotteZoningAdapter(session=session).extract(
            RunOptions(datasets=(DatasetId.ZONING,), county_fips="37119", limit=1)
        )

        self.assertEqual(len(batch.records), 1)
        self.assertEqual(session.calls[0][1]["params"]["where"], "1 = 1")

    def test_rentcast_pagination_is_bounded_to_500_record_pages(self) -> None:
        first_page = [{"id": str(index)} for index in range(500)]
        second_page = [{"id": str(index)} for index in range(500, 501)]
        session = FakeSession([first_page, second_page])

        listings = fetch_rentcast_listings(
            session,
            "https://api.example.test/listings",
            api_key="secret",
            limit=501,
        )

        self.assertEqual(len(listings), 501)
        self.assertEqual(session.calls[0][1]["params"]["limit"], 500)
        self.assertEqual(session.calls[1][1]["params"]["limit"], 1)
        self.assertEqual(session.calls[1][1]["params"]["offset"], 500)
        self.assertEqual(session.calls[0][1]["params"]["state"], "NC")
        self.assertEqual(session.calls[0][1]["headers"], {"X-Api-Key": "secret"})

    def test_rentcast_adapters_skip_without_credentials(self) -> None:
        session = FakeSession([])
        options = RunOptions(
            datasets=(DatasetId.SALE_LISTINGS, DatasetId.RENTAL_LISTINGS), limit=1
        )

        with patch.dict(os.environ, {}, clear=True):
            sale_batch = RentCastSaleAdapter(session=session).extract(options)
            rental_batch = RentCastRentalAdapter(session=session).extract(options)

        self.assertEqual(sale_batch.skipped_reason, "RENTCAST_API_KEY is not configured")
        self.assertEqual(rental_batch.skipped_reason, "RENTCAST_API_KEY is not configured")
        self.assertEqual(session.calls, [])

    def test_rentcast_sale_adapter_extracts_active_nc_listing(self) -> None:
        listing = load_fixture("rentcast_listing.json")
        session = FakeSession([[listing]])

        with patch.dict(os.environ, {"RENTCAST_API_KEY": "test-key"}, clear=True):
            batch = RentCastSaleAdapter(session=session).extract(
                RunOptions(
                    datasets=(DatasetId.SALE_LISTINGS,),
                    county_fips="37183",
                    limit=2,
                )
            )

        self.assertEqual(len(batch.records), 1)
        self.assertEqual(batch.records[0].data["listing_type"], "sale")
        self.assertEqual(session.calls[0][1]["params"]["state"], "NC")
        self.assertEqual(session.calls[0][1]["headers"], {"X-Api-Key": "test-key"})


if __name__ == "__main__":
    unittest.main()
