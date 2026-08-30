from __future__ import annotations

import io
import re
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from pipelines.config import RunOptions
from pipelines.contracts import ExtractedBatch, NormalizedRecord, RecordKind, canonical_hash
from pipelines.sources.arcgis import HTTP_TIMEOUT, HTTPSession, new_session


DATASET_SLUG = "mortgage-balances-delinquencies"
SOURCE_SLUG = "nyfed-household-debt"
WORKBOOK_URL = (
    "https://www.newyorkfed.org/medialibrary/interactives/"
    "householdcredit/data/xls/area_report_by_year.xlsx"
)
QUARTER_PATTERN = re.compile(r"Q([1-4])_(\d{4})$")


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _quarter_end(column: str) -> date | None:
    match = QUARTER_PATTERN.fullmatch(column.strip())
    if not match:
        return None
    quarter, year = int(match.group(1)), int(match.group(2))
    return date(year, quarter * 3, (31, 30, 30, 31)[quarter - 1])


def normalize_nyfed_tables(
    mortgage: pd.DataFrame,
    delinquency: pd.DataFrame,
    *,
    as_of: date,
    include_raw_payload: bool = True,
) -> list[NormalizedRecord]:
    """Normalize the New York Fed state Q4 mortgage series without doing I/O."""
    definitions = (
        (mortgage, "mortgage_balance_per_capita", "USD_per_capita"),
        (delinquency, "mortgage_balance_90_plus_days_delinquent", "percent"),
    )
    records: list[NormalizedRecord] = []
    for frame, metric, unit in definitions:
        state_column = next(
            (column for column in frame.columns if str(column).strip().lower() == "state"),
            None,
        )
        if state_column is None:
            raise ValueError("New York Fed workbook is missing its state column")
        nc_rows = frame[frame[state_column].astype(str).str.strip().str.upper() == "NC"]
        if nc_rows.empty:
            raise ValueError("New York Fed workbook did not contain a North Carolina row")
        row = nc_rows.iloc[0]
        for column in frame.columns:
            period_end = _quarter_end(str(column))
            if period_end is None or period_end > as_of:
                continue
            numeric_value = _number(row[column])
            if numeric_value is None:
                continue
            vintage = str(column)
            raw = {"state": "NC", "metric": metric, "period": vintage, "value": row[column]}
            records.append(
                NormalizedRecord(
                    kind=RecordKind.INDICATOR,
                    source_key=f"37:{metric}:{vintage}",
                    data={
                        "geography_type": "state",
                        "geoid": "37",
                        "metric": metric,
                        "period_start": period_end,
                        "period_end": period_end,
                        "value": numeric_value,
                        "unit": unit,
                        "vintage": vintage,
                        "margin_of_error": None,
                        "suppressed": False,
                    },
                    raw_payload=raw if include_raw_payload else {},
                    content_hash=canonical_hash(raw),
                )
            )
    records.sort(key=lambda record: (record.data["period_end"], record.data["metric"]), reverse=True)
    return records


def parse_nyfed_workbook(content: bytes) -> tuple[pd.DataFrame, pd.DataFrame]:
    workbook = io.BytesIO(content)
    mortgage = pd.read_excel(workbook, sheet_name="mortgage", header=8)
    workbook.seek(0)
    delinquency = pd.read_excel(workbook, sheet_name="mortgage_delinq", header=8)
    return mortgage, delinquency


def fetch_workbook(session: HTTPSession) -> bytes:
    response = session.get(
        WORKBOOK_URL,
        headers={"Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return response.content


class NYFedHouseholdDebtAdapter:
    dataset_slug = DATASET_SLUG
    source_slug = SOURCE_SLUG

    def __init__(self, session: HTTPSession | None = None) -> None:
        self.session = session or new_session()

    def extract(self, options: RunOptions) -> ExtractedBatch:
        retrieved_at = datetime.now(timezone.utc)
        mortgage, delinquency = parse_nyfed_workbook(fetch_workbook(self.session))
        records = normalize_nyfed_tables(
            mortgage,
            delinquency,
            as_of=options.as_of,
            include_raw_payload=options.include_raw_payloads,
        )
        return ExtractedBatch(
            dataset_slug=self.dataset_slug,
            source_slug=self.source_slug,
            source_version=max((record.data["vintage"] for record in records), default=None),
            retrieved_at=retrieved_at,
            records=records[: options.limit],
        )
