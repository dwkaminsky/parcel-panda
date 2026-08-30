from __future__ import annotations

import io
import re
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from pipelines.config import RunOptions
from pipelines.contracts import ExtractedBatch, NormalizedRecord, RecordKind, canonical_hash
from pipelines.sources.arcgis import HTTP_TIMEOUT, HTTPSession, new_session


DATASET_SLUG = "property-tax"
SOURCE_SLUG = "ncdor-property-tax"
RATES_VERSION = "2026-2027"
VALUES_VERSION = "2025-2026"
SOURCE_VERSION = f"rates:{RATES_VERSION};values:{VALUES_VERSION}"
RATES_URL = "https://www.ncdor.gov/2026-2027countytaxratesfinalxlsx/open"
VALUES_URL = "https://www.ncdor.gov/lg01b2025-2026xlsx/open"
RATES_PERIOD = (date(2026, 7, 1), date(2027, 6, 30))
VALUES_PERIOD = (date(2025, 7, 1), date(2026, 6, 30))

# North Carolina's county codes are stable, but the names do not sort directly
# to code order around "McDowell". Keep the official mapping explicit.
NC_COUNTY_FIPS = {
    name: f"37{code:03d}"
    for name, code in (
        ("Alamance", 1), ("Alexander", 3), ("Alleghany", 5), ("Anson", 7),
        ("Ashe", 9), ("Avery", 11), ("Beaufort", 13), ("Bertie", 15),
        ("Bladen", 17), ("Brunswick", 19), ("Buncombe", 21), ("Burke", 23),
        ("Cabarrus", 25), ("Caldwell", 27), ("Camden", 29), ("Carteret", 31),
        ("Caswell", 33), ("Catawba", 35), ("Chatham", 37), ("Cherokee", 39),
        ("Chowan", 41), ("Clay", 43), ("Cleveland", 45), ("Columbus", 47),
        ("Craven", 49), ("Cumberland", 51), ("Currituck", 53), ("Dare", 55),
        ("Davidson", 57), ("Davie", 59), ("Duplin", 61), ("Durham", 63),
        ("Edgecombe", 65), ("Forsyth", 67), ("Franklin", 69), ("Gaston", 71),
        ("Gates", 73), ("Graham", 75), ("Granville", 77), ("Greene", 79),
        ("Guilford", 81), ("Halifax", 83), ("Harnett", 85), ("Haywood", 87),
        ("Henderson", 89), ("Hertford", 91), ("Hoke", 93), ("Hyde", 95),
        ("Iredell", 97), ("Jackson", 99), ("Johnston", 101), ("Jones", 103),
        ("Lee", 105), ("Lenoir", 107), ("Lincoln", 109), ("McDowell", 111),
        ("Macon", 113), ("Madison", 115), ("Martin", 117), ("Mecklenburg", 119),
        ("Mitchell", 121), ("Montgomery", 123), ("Moore", 125), ("Nash", 127),
        ("New Hanover", 129), ("Northampton", 131), ("Onslow", 133), ("Orange", 135),
        ("Pamlico", 137), ("Pasquotank", 139), ("Pender", 141), ("Perquimans", 143),
        ("Person", 145), ("Pitt", 147), ("Polk", 149), ("Randolph", 151),
        ("Richmond", 153), ("Robeson", 155), ("Rockingham", 157), ("Rowan", 159),
        ("Rutherford", 161), ("Sampson", 163), ("Scotland", 165), ("Stanly", 167),
        ("Stokes", 169), ("Surry", 171), ("Swain", 173), ("Transylvania", 175),
        ("Tyrrell", 177), ("Union", 179), ("Vance", 181), ("Wake", 183),
        ("Warren", 185), ("Washington", 187), ("Watauga", 189), ("Wayne", 191),
        ("Wilkes", 193), ("Wilson", 195), ("Yadkin", 197), ("Yancey", 199),
    )
}


def _column(frame: pd.DataFrame, *needles: str) -> str:
    for column in frame.columns:
        normalized = " ".join(str(column).lower().split())
        if all(needle.lower() in normalized for needle in needles):
            return str(column)
    raise ValueError(f"NCDOR workbook is missing a column containing {needles!r}")


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").strip()
        if not cleaned:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        if not match:
            return None
        return float(match.group())
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _indicator(
    *,
    county: str,
    metric: str,
    value: float,
    unit: str,
    vintage: str,
    period: tuple[date, date],
    raw_value: Any,
    include_raw_payload: bool,
) -> NormalizedRecord:
    geoid = NC_COUNTY_FIPS[county]
    raw = {
        "county": county,
        "metric": metric,
        "value": None if pd.isna(raw_value) else raw_value,
        "fiscal_year": vintage,
    }
    return NormalizedRecord(
        kind=RecordKind.INDICATOR,
        source_key=f"{geoid}:{metric}:{vintage}",
        data={
            "geography_type": "county",
            "geoid": geoid,
            "metric": metric,
            "period_start": period[0],
            "period_end": period[1],
            "value": value,
            "unit": unit,
            "vintage": vintage,
            "margin_of_error": None,
            "suppressed": False,
        },
        raw_payload=raw if include_raw_payload else {},
        content_hash=canonical_hash(raw),
    )


def normalize_ncdor_tables(
    rates: pd.DataFrame,
    values: pd.DataFrame,
    *,
    county_fips: str | None = None,
    include_raw_payload: bool = True,
) -> list[NormalizedRecord]:
    """Normalize the two statewide NCDOR county workbooks without doing I/O."""
    records: list[NormalizedRecord] = []
    table_metrics = (
        (
            rates,
            RATES_VERSION,
            RATES_PERIOD,
            (
                (("tax rate",), "county_property_tax_rate", "usd_per_100_assessed"),
                (("latest", "reapp"), "latest_reappraisal_year", "year"),
                (("next", "reapp"), "next_reappraisal_year", "year"),
            ),
        ),
        (
            values,
            VALUES_VERSION,
            VALUES_PERIOD,
            (
                (("residential property",), "residential_assessed_value", "USD"),
                (("commercial property",), "commercial_assessed_value", "USD"),
                (("industrial",), "industrial_assessed_value", "USD"),
                (("total taxable real estate",), "total_taxable_real_estate", "USD"),
            ),
        ),
    )
    for frame, vintage, period, metrics in table_metrics:
        county_column = _column(frame, "count")
        resolved_metrics = [(_column(frame, *needles), metric, unit) for needles, metric, unit in metrics]
        for row in frame.to_dict(orient="records"):
            county = str(row.get(county_column, "")).strip()
            geoid = NC_COUNTY_FIPS.get(county)
            if geoid is None or (county_fips and geoid != county_fips):
                continue
            for column, metric, unit in resolved_metrics:
                numeric_value = _number(row.get(column))
                if numeric_value is None:
                    continue
                records.append(
                    _indicator(
                        county=county,
                        metric=metric,
                        value=numeric_value,
                        unit=unit,
                        vintage=vintage,
                        period=period,
                        raw_value=row.get(column),
                        include_raw_payload=include_raw_payload,
                    )
                )
    records.sort(key=lambda record: (record.data["geoid"], record.data["metric"]))
    return records


def parse_ncdor_workbooks(rates_content: bytes, values_content: bytes) -> tuple[pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_excel(io.BytesIO(rates_content), sheet_name="County Rates", header=1),
        pd.read_excel(io.BytesIO(values_content), sheet_name="Values", header=1),
    )


def fetch_workbook(session: HTTPSession, url: str) -> bytes:
    response = session.get(
        url,
        headers={"Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return response.content


class NCDORPropertyTaxAdapter:
    dataset_slug = DATASET_SLUG
    source_slug = SOURCE_SLUG

    def __init__(self, session: HTTPSession | None = None) -> None:
        self.session = session or new_session()

    def extract(self, options: RunOptions) -> ExtractedBatch:
        retrieved_at = datetime.now(timezone.utc)
        rates, values = parse_ncdor_workbooks(
            fetch_workbook(self.session, RATES_URL),
            fetch_workbook(self.session, VALUES_URL),
        )
        records = normalize_ncdor_tables(
            rates,
            values,
            county_fips=options.county_fips,
            include_raw_payload=options.include_raw_payloads,
        )
        return ExtractedBatch(
            dataset_slug=self.dataset_slug,
            source_slug=self.source_slug,
            source_version=SOURCE_VERSION,
            retrieved_at=retrieved_at,
            records=records[: options.limit],
        )
