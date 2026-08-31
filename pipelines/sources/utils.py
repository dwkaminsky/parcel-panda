from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_datetime(value: Any) -> datetime | None:
    """Parse ArcGIS epoch milliseconds or an ISO-8601 timestamp as UTC."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        if value <= 0:
            return None
        return datetime.fromtimestamp(value / 1_000, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def nc_county_fips(state_fips: Any, county_fips: Any) -> str | None:
    """Return a five-character NC county FIPS code from common API shapes."""
    state = clean_text(state_fips)
    county = clean_text(county_fips)
    if county and len(county) == 5:
        return county if county.startswith("37") else None
    if state != "37" or not county:
        return None
    return f"37{county.zfill(3)}"
