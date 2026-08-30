from __future__ import annotations

import csv
import io
from calendar import monthrange
from datetime import date, datetime, timezone
from typing import Literal

from pipelines.config import RunOptions
from pipelines.contracts import ExtractedBatch, NormalizedRecord, RecordKind, canonical_hash
from pipelines.sources.arcgis import HTTP_TIMEOUT, HTTPSession, new_session


DATASET_SLUG = "mortgage-balances-delinquencies"
SOURCE_SLUG = "cfpb-mortgage-performance"
SOURCE_VERSION = "2025-12"
EARLY_DELINQUENCY_URL = (
    "https://files.consumerfinance.gov/data/mortgage-performance/downloads/"
    "CountyMortgagesPercent-30-89DaysLate-thru-2025-12.csv"
)
SERIOUS_DELINQUENCY_URL = (
    "https://files.consumerfinance.gov/data/mortgage-performance/downloads/"
    "CountyMortgagesPercent-90-plusDaysLate-thru-2025-12.csv"
)

CFPBMetric = Literal[
    "mortgages_30_89_days_delinquent",
    "mortgages_90_plus_days_delinquent",
]


def parse_cfpb_csv(csv_text: str) -> list[dict[str, str]]:
    """Parse a CFPB county CSV without performing I/O."""
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    required = {"RegionType", "State", "Name", "FIPSCode"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        missing = sorted(required.difference(reader.fieldnames or ()))
        raise ValueError(f"CFPB CSV is missing required column(s): {', '.join(missing)}")
    return [dict(row) for row in reader]


def _clean_fips(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip("'").strip('"')
    return cleaned if len(cleaned) == 5 and cleaned.isdigit() else None


def _parse_rate(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().rstrip("%").strip()
    if not cleaned or cleaned.lower() in {"na", "n/a", "null", "."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _month_period(column: str) -> tuple[date, date] | None:
    try:
        period_start = datetime.strptime(column.strip(), "%Y-%m").date()
    except ValueError:
        return None
    return period_start, date(
        period_start.year,
        period_start.month,
        monthrange(period_start.year, period_start.month)[1],
    )


def normalize_cfpb_county_rows(
    rows: list[dict[str, str]],
    *,
    metric: CFPBMetric,
    as_of: date,
    county_fips: str | None = None,
    include_raw_payload: bool = True,
) -> list[NormalizedRecord]:
    """Normalize CFPB wide county rows into monthly NC indicator observations."""
    records: list[NormalizedRecord] = []
    for row in rows:
        geoid = _clean_fips(row.get("FIPSCode"))
        state = (row.get("State") or "").strip().upper()
        region_type = (row.get("RegionType") or "").strip().lower()
        if (
            region_type != "county"
            or state != "NC"
            or geoid is None
            or not geoid.startswith("37")
            or (county_fips and geoid != county_fips)
        ):
            continue

        for column, raw_value in row.items():
            period = _month_period(column)
            if period is None:
                continue
            period_start, period_end = period
            if period_end > as_of:
                continue
            value = _parse_rate(raw_value)
            raw_observation = {
                "RegionType": row.get("RegionType"),
                "State": row.get("State"),
                "Name": row.get("Name"),
                "FIPSCode": row.get("FIPSCode"),
                "period": column,
                "value": raw_value,
                "metric": metric,
            }
            records.append(
                NormalizedRecord(
                    kind=RecordKind.INDICATOR,
                    source_key=f"{geoid}:{metric}:{column}",
                    data={
                        "geography_type": "county",
                        "geoid": geoid,
                        "metric": metric,
                        "period_start": period_start,
                        "period_end": period_end,
                        "value": value,
                        "unit": "percent",
                        "vintage": SOURCE_VERSION,
                        "margin_of_error": None,
                        "suppressed": value is None,
                    },
                    raw_payload=raw_observation if include_raw_payload else {},
                    content_hash=canonical_hash(raw_observation),
                )
            )
    return records


def fetch_cfpb_csv(session: HTTPSession, url: str) -> str:
    """Download a CFPB CSV using the pipeline's bounded HTTP timeout."""
    response = session.get(
        url,
        headers={"Accept": "text/csv"},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return response.text


class CFPBMortgagePerformanceAdapter:
    dataset_slug = DATASET_SLUG
    source_slug = SOURCE_SLUG

    def __init__(self, session: HTTPSession | None = None) -> None:
        self.session = session or new_session()

    def extract(self, options: RunOptions) -> ExtractedBatch:
        retrieved_at = datetime.now(timezone.utc)
        inputs: tuple[tuple[str, CFPBMetric], ...] = (
            (EARLY_DELINQUENCY_URL, "mortgages_30_89_days_delinquent"),
            (SERIOUS_DELINQUENCY_URL, "mortgages_90_plus_days_delinquent"),
        )
        records: list[NormalizedRecord] = []
        for url, metric in inputs:
            rows = parse_cfpb_csv(fetch_cfpb_csv(self.session, url))
            records.extend(
                normalize_cfpb_county_rows(
                    rows,
                    metric=metric,
                    as_of=options.as_of,
                    county_fips=options.county_fips,
                    include_raw_payload=options.include_raw_payloads,
                )
            )

        records.sort(
            key=lambda record: (
                record.data["period_end"],
                record.data["geoid"],
                record.data["metric"],
            ),
            reverse=True,
        )
        return ExtractedBatch(
            dataset_slug=self.dataset_slug,
            source_slug=self.source_slug,
            source_version=SOURCE_VERSION,
            retrieved_at=retrieved_at,
            records=records[: options.limit],
        )
