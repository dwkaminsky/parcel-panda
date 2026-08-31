from __future__ import annotations

from datetime import date

import pandas as pd

from pipelines.sources.ncdor import normalize_ncdor_tables
from pipelines.sources.nyfed import normalize_nyfed_tables


def test_ncdor_normalizes_tax_rates_reappraisals_and_assessed_values() -> None:
    rates = pd.DataFrame(
        [
            {
                "Counties": "Wake",
                "Tax Rate\n[Notes 1,2]": 0.5135,
                "Year of Latest Reappraisal": 2024,
                "Next Scheduled Reappraisal": "2028*",
            },
            {
                "Counties": "Durham",
                "Tax Rate\n[Notes 1,2]": 0.65,
                "Year of Latest Reappraisal": 2025,
                "Next Scheduled Reappraisal": 2029,
            },
        ]
    )
    values = pd.DataFrame(
        [
            {
                "Counties": "Wake",
                "Residential Property": 100,
                "Commercial Property": 50,
                "Industrial": 25,
                "Total Taxable Real Estate": 175,
            }
        ]
    )

    records = normalize_ncdor_tables(rates, values, county_fips="37183")

    assert len(records) == 7
    assert {record.data["geoid"] for record in records} == {"37183"}
    by_metric = {record.data["metric"]: record for record in records}
    assert by_metric["county_property_tax_rate"].data["value"] == 0.5135
    assert by_metric["county_property_tax_rate"].data["vintage"] == "2026-2027"
    assert by_metric["next_reappraisal_year"].data["value"] == 2028.0
    assert by_metric["total_taxable_real_estate"].data["value"] == 175.0
    assert by_metric["total_taxable_real_estate"].data["vintage"] == "2025-2026"


def test_nyfed_normalizes_latest_state_balances_and_delinquencies() -> None:
    mortgage = pd.DataFrame(
        [{"state": "NC", "Q4_2024": 20_100, "Q4_2025": 21_200}]
    )
    delinquency = pd.DataFrame(
        [{"state": "NC", "Q4_2024": 1.25, "Q4_2025": 1.5}]
    )

    records = normalize_nyfed_tables(
        mortgage,
        delinquency,
        as_of=date(2025, 1, 1),
        include_raw_payload=False,
    )

    assert len(records) == 2
    assert {record.data["vintage"] for record in records} == {"Q4_2024"}
    assert {record.data["geography_type"] for record in records} == {"state"}
    assert {record.data["geoid"] for record in records} == {"37"}
    assert all(record.raw_payload == {} for record in records)
