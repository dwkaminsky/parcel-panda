from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from pipelines.config import RunOptions
from pipelines.contracts import ExtractedBatch, NormalizedRecord, RecordKind, canonical_hash
from pipelines.sources.arcgis import HTTP_TIMEOUT, HTTPSession, new_session


DATASET_SLUG = "housing-demographics"
SOURCE_SLUG = "census-acs5"
ACS_VINTAGE = 2024
ACS_PROFILE_URL = f"https://api.census.gov/data/{ACS_VINTAGE}/acs/acs5/profile"
CREDENTIAL_ENV_VAR = "CENSUS_API_KEY"
NC_STATE_FIPS = "37"
SUPPRESSION_FLOOR = -100_000_000


@dataclass(frozen=True)
class ACSMetric:
    estimate: str
    margin_of_error: str
    name: str
    unit: str


ACS_METRICS = (
    ACSMetric("DP05_0001E", "DP05_0001M", "total_population", "count"),
    ACSMetric("DP04_0001E", "DP04_0001M", "total_housing_units", "count"),
    ACSMetric("DP04_0046PE", "DP04_0046PM", "owner_occupied_share", "percent"),
    ACSMetric("DP04_0089E", "DP04_0089M", "median_owner_occupied_home_value", "USD"),
    ACSMetric("DP04_0134E", "DP04_0134M", "median_gross_rent", "USD"),
)


def parse_census_response(payload: Any) -> list[dict[str, str]]:
    """Convert the Census API's header-plus-rows response into dictionaries."""
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        raise ValueError("Census response was not a header-plus-rows array")
    header = payload[0]
    if not all(isinstance(column, str) for column in header):
        raise ValueError("Census response header contained a non-string column")
    required = {"NAME", "state", "county"}
    if not required.issubset(header):
        missing = sorted(required.difference(header))
        raise ValueError(f"Census response is missing required column(s): {', '.join(missing)}")

    rows: list[dict[str, str]] = []
    for values in payload[1:]:
        if not isinstance(values, list) or len(values) != len(header):
            raise ValueError("Census response row did not match the header length")
        rows.append({column: str(value) for column, value in zip(header, values)})
    return rows


def _estimate(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return None if parsed <= SUPPRESSION_FLOOR else parsed


def normalize_census_county_rows(
    rows: list[dict[str, str]],
    *,
    vintage: int = ACS_VINTAGE,
    county_fips: str | None = None,
    include_raw_payload: bool = True,
) -> list[NormalizedRecord]:
    """Normalize ACS profile estimate/MOE pairs for North Carolina counties."""
    period_start = date(vintage - 4, 1, 1)
    period_end = date(vintage, 12, 31)
    vintage_name = f"{vintage} ACS 5-year"
    records: list[NormalizedRecord] = []

    for row in rows:
        state = row.get("state", "").zfill(2)
        county = row.get("county", "").zfill(3)
        geoid = f"{state}{county}"
        if state != NC_STATE_FIPS or (county_fips and geoid != county_fips):
            continue

        for definition in ACS_METRICS:
            value = _estimate(row.get(definition.estimate))
            margin_of_error = _estimate(row.get(definition.margin_of_error))
            raw_observation = {
                "NAME": row.get("NAME"),
                "state": state,
                "county": county,
                "estimate_variable": definition.estimate,
                "estimate": row.get(definition.estimate),
                "moe_variable": definition.margin_of_error,
                "margin_of_error": row.get(definition.margin_of_error),
            }
            records.append(
                NormalizedRecord(
                    kind=RecordKind.INDICATOR,
                    source_key=f"{geoid}:{definition.name}:{vintage}",
                    data={
                        "geography_type": "county",
                        "geoid": geoid,
                        "metric": definition.name,
                        "period_start": period_start,
                        "period_end": period_end,
                        "value": value,
                        "unit": definition.unit,
                        "vintage": vintage_name,
                        "margin_of_error": margin_of_error,
                        "suppressed": value is None,
                    },
                    raw_payload=raw_observation if include_raw_payload else {},
                    content_hash=canonical_hash(raw_observation),
                )
            )
    return records


def fetch_census_counties(
    session: HTTPSession,
    *,
    api_key: str,
    county_fips: str | None = None,
) -> Any:
    variables = ["NAME"]
    for definition in ACS_METRICS:
        variables.extend((definition.estimate, definition.margin_of_error))
    county = county_fips[-3:] if county_fips else "*"
    response = session.get(
        ACS_PROFILE_URL,
        params={
            "get": ",".join(variables),
            "for": f"county:{county}",
            "in": f"state:{NC_STATE_FIPS}",
            "key": api_key,
        },
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


class CensusACS5Adapter:
    dataset_slug = DATASET_SLUG
    source_slug = SOURCE_SLUG
    credential_env_var = CREDENTIAL_ENV_VAR

    def __init__(self, session: HTTPSession | None = None) -> None:
        self.session = session or new_session()

    def extract(self, options: RunOptions) -> ExtractedBatch:
        retrieved_at = datetime.now(timezone.utc)
        api_key = os.getenv(self.credential_env_var, "").strip()
        if not api_key:
            return ExtractedBatch(
                dataset_slug=self.dataset_slug,
                source_slug=self.source_slug,
                source_version=str(ACS_VINTAGE),
                retrieved_at=retrieved_at,
                skipped_reason=f"{self.credential_env_var} is not configured",
            )

        payload = fetch_census_counties(
            self.session,
            api_key=api_key,
            county_fips=options.county_fips,
        )
        records = normalize_census_county_rows(
            parse_census_response(payload),
            county_fips=options.county_fips,
            include_raw_payload=options.include_raw_payloads,
        )
        records.sort(key=lambda record: (record.data["geoid"], record.data["metric"]))
        return ExtractedBatch(
            dataset_slug=self.dataset_slug,
            source_slug=self.source_slug,
            source_version=str(ACS_VINTAGE),
            retrieved_at=retrieved_at,
            records=records[: options.limit],
        )
