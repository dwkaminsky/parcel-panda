from __future__ import annotations

from typing import TypedDict


class DatasetDefinition(TypedDict):
    slug: str
    name: str
    category: str
    status: str
    geography_grain: str
    cadence: str


class SourceDefinition(TypedDict):
    slug: str
    name: str
    publisher: str
    source_url: str
    access_type: str
    credential_env_var: str | None


DATASETS: tuple[DatasetDefinition, ...] = (
    {"slug": "parcel-records", "name": "Parcel records & assessed values", "category": "Parcels & ownership", "status": "partial", "geography_grain": "county", "cadence": "varies by county"},
    {"slug": "ownership-boundaries", "name": "Ownership & parcel boundaries", "category": "Parcels & ownership", "status": "identified", "geography_grain": "county", "cadence": "varies by county"},
    {"slug": "property-tax", "name": "Tax assessed values & property tax", "category": "Values & taxes", "status": "planned", "geography_grain": "county", "cadence": "annual"},
    {"slug": "mortgage-balances-delinquencies", "name": "Mortgage balances & delinquencies", "category": "Financing & mortgages", "status": "identified", "geography_grain": "county and state", "cadence": "monthly and annual"},
    {"slug": "active-sale-listings", "name": "Active for-sale listings", "category": "Sales & listings", "status": "planned", "geography_grain": "property", "cadence": "daily"},
    {"slug": "active-rental-listings", "name": "Active rental listings", "category": "Sales & listings", "status": "planned", "geography_grain": "property", "cadence": "daily"},
    {"slug": "housing-demographics", "name": "Housing & neighborhood context", "category": "Neighborhood context", "status": "identified", "geography_grain": "census geography", "cadence": "annual"},
    {"slug": "flood-hazards", "name": "Flood hazards & elevation", "category": "Hazards & environment", "status": "identified", "geography_grain": "spatial", "cadence": "source-specific"},
    {"slug": "zoning-land-use", "name": "Zoning & future land use", "category": "Development & land use", "status": "identified", "geography_grain": "municipal", "cadence": "monthly"},
)


SOURCES: tuple[SourceDefinition, ...] = (
    {"slug": "nc-onemap-parcels", "name": "NC OneMap Parcels", "publisher": "NC Geographic Information Coordinating Council", "source_url": "https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/FeatureServer", "access_type": "public", "credential_env_var": None},
    {"slug": "ncdor-property-tax", "name": "Property Tax Reports and Statistics", "publisher": "North Carolina Department of Revenue", "source_url": "https://www.ncdor.gov/taxes-forms/property-tax", "access_type": "public", "credential_env_var": None},
    {"slug": "cfpb-mortgage-performance", "name": "Mortgage Performance Trends", "publisher": "Consumer Financial Protection Bureau", "source_url": "https://www.consumerfinance.gov/data-research/mortgage-performance-trends/download-the-data/", "access_type": "public", "credential_env_var": None},
    {"slug": "nyfed-household-debt", "name": "Household Debt and Credit Data Bank", "publisher": "Federal Reserve Bank of New York", "source_url": "https://www.newyorkfed.org/microeconomics/databank.html", "access_type": "public", "credential_env_var": None},
    {"slug": "census-acs5", "name": "American Community Survey 5-Year Data API", "publisher": "U.S. Census Bureau", "source_url": "https://api.census.gov/data/2024/acs/acs5/profile", "access_type": "public", "credential_env_var": "CENSUS_API_KEY"},
    {"slug": "ncem-fris", "name": "NC Emergency Management Flood Risk Information System", "publisher": "North Carolina Emergency Management", "source_url": "https://spartagis.ncem.org/arcgis/rest/services/Public/FRIS_FloodZones/MapServer", "access_type": "public", "credential_env_var": None},
    {"slug": "charlotte-zoning", "name": "Charlotte Zoning", "publisher": "City of Charlotte", "source_url": "https://gis.charlottenc.gov/arcgis/rest/services/PLN/Zoning/MapServer/0", "access_type": "public", "credential_env_var": None},
    {"slug": "rentcast-sale", "name": "Property Listings API", "publisher": "RentCast", "source_url": "https://api.rentcast.io/v1/listings/sale", "access_type": "licensed", "credential_env_var": "RENTCAST_API_KEY"},
    {"slug": "rentcast-rental", "name": "Long-term Rental Listings API", "publisher": "RentCast", "source_url": "https://api.rentcast.io/v1/listings/rental/long-term", "access_type": "licensed", "credential_env_var": "RENTCAST_API_KEY"},
)


DATASET_SOURCES: tuple[tuple[str, str], ...] = (
    ("parcel-records", "nc-onemap-parcels"),
    ("ownership-boundaries", "nc-onemap-parcels"),
    ("property-tax", "nc-onemap-parcels"),
    ("property-tax", "ncdor-property-tax"),
    ("mortgage-balances-delinquencies", "cfpb-mortgage-performance"),
    ("mortgage-balances-delinquencies", "nyfed-household-debt"),
    ("active-sale-listings", "rentcast-sale"),
    ("active-rental-listings", "rentcast-rental"),
    ("housing-demographics", "census-acs5"),
    ("flood-hazards", "ncem-fris"),
    ("zoning-land-use", "charlotte-zoning"),
)
