from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.base import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    parcel_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
    )

    address: Mapped[str | None] = mapped_column(
        String(300),
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
    )

    state: Mapped[str | None] = mapped_column(
        String(2),
    )

    zip_code: Mapped[str | None] = mapped_column(
        String(10),
    )

    latitude: Mapped[float | None] = mapped_column(
        Float,
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
    )

    assessed_value: Mapped[float | None] = mapped_column(
        Numeric(14, 2),
    )

    source: Mapped[str | None] = mapped_column(
        String(100),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class CatalogDataset(Base):
    __tablename__ = "catalog_datasets"

    slug: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24))
    geography_grain: Mapped[str] = mapped_column(String(50))
    cadence: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'partial', 'in-development', 'planned', 'identified')",
            name="ck_catalog_datasets_status",
        ),
    )


class DataSource(Base):
    __tablename__ = "data_sources"

    slug: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    publisher: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(Text)
    access_type: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    credential_env_var: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "access_type IN ('public', 'licensed')",
            name="ck_data_sources_access_type",
        ),
    )


class DatasetSource(Base):
    __tablename__ = "dataset_sources"

    dataset_slug: Mapped[str] = mapped_column(
        ForeignKey("catalog_datasets.slug", ondelete="CASCADE"),
        primary_key=True,
    )
    source_slug: Mapped[str] = mapped_column(
        ForeignKey("data_sources.slug", ondelete="CASCADE"),
        primary_key=True,
    )


class Geography(Base):
    __tablename__ = "geographies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    geography_type: Mapped[str] = mapped_column(String(32))
    geoid: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    state_code: Mapped[str | None] = mapped_column(String(2))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("geographies.id"))

    __table_args__ = (
        UniqueConstraint("geography_type", "geoid", name="uq_geographies_type_geoid"),
        Index("ix_geographies_parent_id", "parent_id"),
        CheckConstraint(
            "geography_type IN ('state', 'county', 'place', 'tract', 'block_group', 'metro', 'non_metro', 'municipal', 'custom')",
            name="ck_geographies_type",
        ),
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    dataset_slug: Mapped[str] = mapped_column(ForeignKey("catalog_datasets.slug"))
    source_slug: Mapped[str] = mapped_column(ForeignKey("data_sources.slug"))
    prefect_flow_run_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    source_version: Mapped[str | None] = mapped_column(String(200))
    extracted_count: Mapped[int] = mapped_column(Integer, default=0)
    loaded_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index(
            "ix_ingestion_runs_dataset_source_started",
            "dataset_slug",
            "source_slug",
            "started_at",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'cancelled')",
            name="ck_ingestion_runs_status",
        ),
        CheckConstraint(
            "extracted_count >= 0 AND loaded_count >= 0 AND unchanged_count >= 0 AND error_count >= 0",
            name="ck_ingestion_runs_counts",
        ),
    )


class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_slug: Mapped[str] = mapped_column(ForeignKey("data_sources.slug"))
    source_key: Mapped[str] = mapped_column(String(300))
    content_hash: Mapped[str] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID] = mapped_column(ForeignKey("ingestion_runs.id"))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict | list | None] = mapped_column(JSON)

    __table_args__ = (
        Index("ix_source_records_source_key", "source_slug", "source_key"),
        UniqueConstraint(
            "source_slug",
            "source_key",
            "content_hash",
            name="uq_source_records_version",
        ),
    )


class PropertyRecord(Base):
    __tablename__ = "property_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"))
    source_slug: Mapped[str] = mapped_column(ForeignKey("data_sources.slug"))
    county_fips: Mapped[str] = mapped_column(String(5))
    parcel_id: Mapped[str] = mapped_column(String(150))
    owner_name: Mapped[str | None] = mapped_column(String(300))
    address: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    zip_code: Mapped[str | None] = mapped_column(String(10))
    acreage: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    land_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    building_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    assessed_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    geometry: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_property_records_county", "county_fips"),
        UniqueConstraint(
            "source_slug",
            "county_fips",
            "parcel_id",
            name="uq_property_records_source_parcel",
        ),
        CheckConstraint("acreage IS NULL OR acreage >= 0", name="ck_property_records_acreage"),
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_property_records_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_property_records_longitude",
        ),
    )


class IndicatorObservation(Base):
    __tablename__ = "indicator_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"))
    dataset_slug: Mapped[str] = mapped_column(ForeignKey("catalog_datasets.slug"))
    source_slug: Mapped[str] = mapped_column(ForeignKey("data_sources.slug"))
    geography_type: Mapped[str] = mapped_column(String(32))
    geoid: Mapped[str] = mapped_column(String(32))
    metric: Mapped[str] = mapped_column(String(120))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    unit: Mapped[str] = mapped_column(String(32))
    vintage: Mapped[str] = mapped_column(String(50), default="")
    margin_of_error: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ix_indicator_observations_lookup",
            "dataset_slug",
            "metric",
            "geoid",
            "period_end",
        ),
        UniqueConstraint(
            "dataset_slug",
            "source_slug",
            "geography_type",
            "geoid",
            "metric",
            "period_start",
            "period_end",
            "vintage",
            name="uq_indicator_observations_natural",
        ),
        CheckConstraint("period_end >= period_start", name="ck_indicator_observations_period"),
        CheckConstraint(
            "margin_of_error IS NULL OR margin_of_error >= 0",
            name="ck_indicator_observations_moe",
        ),
    )


class ListingRecord(Base):
    __tablename__ = "listing_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"))
    source_slug: Mapped[str] = mapped_column(ForeignKey("data_sources.slug"))
    listing_type: Mapped[str] = mapped_column(String(12))
    source_listing_id: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    zip_code: Mapped[str | None] = mapped_column(String(10))
    county_fips: Mapped[str | None] = mapped_column(String(5))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    asking_price: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    bedrooms: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    bathrooms: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    square_feet: Mapped[int | None] = mapped_column(Integer)
    property_type: Mapped[str | None] = mapped_column(String(100))
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "source_slug",
            "listing_type",
            "source_listing_id",
            name="uq_listing_records_source_listing",
        ),
        CheckConstraint("listing_type IN ('sale', 'rental')", name="ck_listing_records_type"),
        CheckConstraint("asking_price IS NULL OR asking_price >= 0", name="ck_listing_records_price"),
    )


class SpatialFeature(Base):
    __tablename__ = "spatial_features"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"))
    dataset_slug: Mapped[str] = mapped_column(ForeignKey("catalog_datasets.slug"))
    source_slug: Mapped[str] = mapped_column(ForeignKey("data_sources.slug"))
    source_layer: Mapped[str] = mapped_column(String(200))
    source_feature_id: Mapped[str] = mapped_column(String(200))
    feature_type: Mapped[str] = mapped_column(String(50))
    name: Mapped[str | None] = mapped_column(String(300))
    jurisdiction: Mapped[str | None] = mapped_column(String(200))
    geometry: Mapped[dict | None] = mapped_column(JSON)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "source_slug",
            "source_layer",
            "source_feature_id",
            name="uq_spatial_features_source_feature",
        ),
    )
