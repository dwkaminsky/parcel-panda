from __future__ import annotations

import json
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from pipelines.config import DatasetId, RunOptions
from pipelines.contracts import RecordKind
from pipelines.sources.census import (
    ACS_PROFILE_URL,
    CensusACS5Adapter,
    normalize_census_county_rows,
    parse_census_response,
)
from pipelines.sources.cfpb import (
    CFPBMortgagePerformanceAdapter,
    EARLY_DELINQUENCY_URL,
    SERIOUS_DELINQUENCY_URL,
    normalize_cfpb_county_rows,
    parse_cfpb_csv,
)


FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, *, text: str = "", payload=None) -> None:
        self.text = text
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def census_payload():
    return json.loads(fixture_text("census_acs5_counties.json"))


class CFPBConnectorTests(unittest.TestCase):
    def test_normalizes_only_requested_nc_county_through_as_of_date(self) -> None:
        rows = parse_cfpb_csv(fixture_text("cfpb_county_delinquency.csv"))

        records = normalize_cfpb_county_rows(
            rows,
            metric="mortgages_30_89_days_delinquent",
            as_of=date(2025, 1, 31),
            county_fips="37183",
        )

        self.assertEqual(len(records), 2)
        latest = records[-1]
        self.assertEqual(latest.kind, RecordKind.INDICATOR)
        self.assertEqual(latest.source_key, "37183:mortgages_30_89_days_delinquent:2025-01")
        self.assertEqual(latest.data["value"], 1.3)
        self.assertEqual(latest.data["period_start"], date(2025, 1, 1))
        self.assertEqual(latest.data["period_end"], date(2025, 1, 31))
        self.assertEqual(latest.data["unit"], "percent")

    def test_marks_missing_cfpb_rate_as_suppressed(self) -> None:
        rows = parse_cfpb_csv(fixture_text("cfpb_county_delinquency.csv"))

        records = normalize_cfpb_county_rows(
            rows,
            metric="mortgages_90_plus_days_delinquent",
            as_of=date(2025, 2, 28),
            county_fips="37183",
        )

        self.assertIsNone(records[-1].data["value"])
        self.assertTrue(records[-1].data["suppressed"])

    def test_adapter_fetches_both_official_csvs_with_timeouts_and_limit(self) -> None:
        csv_text = fixture_text("cfpb_county_delinquency.csv")
        session = FakeSession(
            [FakeResponse(text=csv_text), FakeResponse(text=csv_text)]
        )

        batch = CFPBMortgagePerformanceAdapter(session=session).extract(
            RunOptions(
                datasets=(DatasetId.MORTGAGE,),
                county_fips="37183",
                as_of=date(2025, 2, 28),
                limit=3,
            )
        )

        self.assertEqual(len(batch.records), 3)
        self.assertEqual(
            [call[0] for call in session.calls],
            [EARLY_DELINQUENCY_URL, SERIOUS_DELINQUENCY_URL],
        )
        self.assertEqual(session.calls[0][1]["timeout"], (5, 45))
        self.assertEqual(session.calls[0][1]["headers"], {"Accept": "text/csv"})


class CensusConnectorTests(unittest.TestCase):
    def test_normalizes_estimates_moes_and_filters_to_nc(self) -> None:
        rows = parse_census_response(census_payload())

        records = normalize_census_county_rows(rows, county_fips="37183")

        self.assertEqual(len(records), 5)
        population = next(record for record in records if record.data["metric"] == "total_population")
        self.assertEqual(population.kind, RecordKind.INDICATOR)
        self.assertEqual(population.data["geoid"], "37183")
        self.assertEqual(population.data["value"], 1152149.0)
        self.assertEqual(population.data["margin_of_error"], 100.0)
        self.assertEqual(population.data["period_start"], date(2020, 1, 1))
        self.assertEqual(population.data["period_end"], date(2024, 12, 31))

    def test_handles_census_suppression_sentinels(self) -> None:
        rows = parse_census_response(census_payload())

        records = normalize_census_county_rows(rows, county_fips="37001")
        population = next(record for record in records if record.data["metric"] == "total_population")

        self.assertIsNone(population.data["value"])
        self.assertIsNone(population.data["margin_of_error"])
        self.assertTrue(population.data["suppressed"])

    def test_adapter_skips_without_census_api_key(self) -> None:
        session = FakeSession([])
        with patch.dict(os.environ, {}, clear=True):
            batch = CensusACS5Adapter(session=session).extract(
                RunOptions(datasets=(DatasetId.HOUSING_DEMOGRAPHICS,), limit=5)
            )

        self.assertEqual(batch.skipped_reason, "CENSUS_API_KEY is not configured")
        self.assertEqual(session.calls, [])

    def test_adapter_queries_nc_county_and_applies_record_limit(self) -> None:
        session = FakeSession([FakeResponse(payload=census_payload())])
        with patch.dict(os.environ, {"CENSUS_API_KEY": "test-key"}, clear=True):
            batch = CensusACS5Adapter(session=session).extract(
                RunOptions(
                    datasets=(DatasetId.HOUSING_DEMOGRAPHICS,),
                    county_fips="37183",
                    limit=2,
                )
            )

        self.assertEqual(len(batch.records), 2)
        self.assertEqual(session.calls[0][0], ACS_PROFILE_URL)
        params = session.calls[0][1]["params"]
        self.assertEqual(params["for"], "county:183")
        self.assertEqual(params["in"], "state:37")
        self.assertEqual(params["key"], "test-key")
        self.assertIn("DP04_0089E", params["get"])
        self.assertEqual(session.calls[0][1]["timeout"], (5, 45))


if __name__ == "__main__":
    unittest.main()
