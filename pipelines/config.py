from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class DatasetId(StrEnum):
    PARCEL_RECORDS = "parcel-records"
    OWNERSHIP_BOUNDARIES = "ownership-boundaries"
    PROPERTY_TAX = "property-tax"
    MORTGAGE = "mortgage-balances-delinquencies"
    SALE_LISTINGS = "active-sale-listings"
    RENTAL_LISTINGS = "active-rental-listings"
    HOUSING_DEMOGRAPHICS = "housing-demographics"
    FLOOD_HAZARDS = "flood-hazards"
    ZONING = "zoning-land-use"


DEFAULT_DATASETS = (
    DatasetId.PARCEL_RECORDS,
    DatasetId.PROPERTY_TAX,
    DatasetId.MORTGAGE,
    DatasetId.HOUSING_DEMOGRAPHICS,
)


class RunOptions(BaseModel):
    datasets: tuple[DatasetId, ...] = DEFAULT_DATASETS
    state: str = "NC"
    county_fips: str | None = None
    as_of: date = Field(default_factory=date.today)
    dry_run: bool = True
    limit: int = Field(default=500, ge=1, le=5_000)
    include_raw_payloads: bool = True

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized != "NC":
            raise ValueError("The initial pipeline release supports North Carolina only")
        return normalized

    @field_validator("county_fips")
    @classmethod
    def validate_county_fips(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) == 3:
            normalized = f"37{normalized}"
        if len(normalized) != 5 or not normalized.isdigit() or not normalized.startswith("37"):
            raise ValueError("county_fips must be a five-digit North Carolina county FIPS code")
        return normalized
