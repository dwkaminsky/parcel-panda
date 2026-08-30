"""create pipeline data models

Revision ID: 8c431d679a1a
Revises: 27aa96de53cd
Create Date: 2026-08-30 13:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c431d679a1a"
down_revision: Union[str, Sequence[str], None] = "27aa96de53cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_datasets",
        sa.Column("slug", sa.String(length=100), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("geography_grain", sa.String(length=50), nullable=False),
        sa.Column("cadence", sa.String(length=100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('available', 'partial', 'in-development', 'planned', 'identified')",
            name="ck_catalog_datasets_status",
        ),
    )
    op.create_table(
        "data_sources",
        sa.Column("slug", sa.String(length=100), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("publisher", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("access_type", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("credential_env_var", sa.String(length=100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "access_type IN ('public', 'licensed')",
            name="ck_data_sources_access_type",
        ),
    )
    op.create_table(
        "dataset_sources",
        sa.Column(
            "dataset_slug",
            sa.String(length=100),
            sa.ForeignKey("catalog_datasets.slug", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_slug",
            sa.String(length=100),
            sa.ForeignKey("data_sources.slug", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "geographies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("geography_type", sa.String(length=32), nullable=False),
        sa.Column("geoid", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("state_code", sa.String(length=2), nullable=True),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey("geographies.id"), nullable=True),
        sa.UniqueConstraint("geography_type", "geoid", name="uq_geographies_type_geoid"),
        sa.CheckConstraint(
            "geography_type IN ('state', 'county', 'place', 'tract', 'block_group', 'metro', 'non_metro', 'municipal', 'custom')",
            name="ck_geographies_type",
        ),
    )
    op.create_index("ix_geographies_parent_id", "geographies", ["parent_id"])
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_slug", sa.String(length=100), sa.ForeignKey("catalog_datasets.slug"), nullable=False),
        sa.Column("source_slug", sa.String(length=100), sa.ForeignKey("data_sources.slug"), nullable=False),
        sa.Column("prefect_flow_run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=200), nullable=True),
        sa.Column("extracted_count", sa.Integer(), nullable=False),
        sa.Column("loaded_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'cancelled')",
            name="ck_ingestion_runs_status",
        ),
        sa.CheckConstraint(
            "extracted_count >= 0 AND loaded_count >= 0 AND unchanged_count >= 0 AND error_count >= 0",
            name="ck_ingestion_runs_counts",
        ),
    )
    op.create_index(
        "ix_ingestion_runs_dataset_source_started",
        "ingestion_runs",
        ["dataset_slug", "source_slug", "started_at"],
    )
    op.create_index(
        "ix_ingestion_runs_prefect_flow_run_id",
        "ingestion_runs",
        ["prefect_flow_run_id"],
    )
    op.create_table(
        "source_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_slug", sa.String(length=100), sa.ForeignKey("data_sources.slug"), nullable=False),
        sa.Column("source_key", sa.String(length=300), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), sa.ForeignKey("ingestion_runs.id"), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.UniqueConstraint("source_slug", "source_key", "content_hash", name="uq_source_records_version"),
    )
    op.create_index("ix_source_records_source_key", "source_records", ["source_slug", "source_key"])
    op.create_table(
        "property_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_record_id", sa.BigInteger(), sa.ForeignKey("source_records.id"), nullable=False),
        sa.Column("source_slug", sa.String(length=100), sa.ForeignKey("data_sources.slug"), nullable=False),
        sa.Column("county_fips", sa.String(length=5), nullable=False),
        sa.Column("parcel_id", sa.String(length=150), nullable=False),
        sa.Column("owner_name", sa.String(length=300), nullable=True),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("zip_code", sa.String(length=10), nullable=True),
        sa.Column("acreage", sa.Numeric(14, 4), nullable=True),
        sa.Column("land_value", sa.Numeric(16, 2), nullable=True),
        sa.Column("building_value", sa.Numeric(16, 2), nullable=True),
        sa.Column("assessed_value", sa.Numeric(16, 2), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("geometry", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_slug", "county_fips", "parcel_id", name="uq_property_records_source_parcel"),
        sa.CheckConstraint("acreage IS NULL OR acreage >= 0", name="ck_property_records_acreage"),
        sa.CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_property_records_latitude"),
        sa.CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_property_records_longitude"),
    )
    op.create_index("ix_property_records_county", "property_records", ["county_fips"])
    op.create_table(
        "indicator_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_record_id", sa.BigInteger(), sa.ForeignKey("source_records.id"), nullable=False),
        sa.Column("dataset_slug", sa.String(length=100), sa.ForeignKey("catalog_datasets.slug"), nullable=False),
        sa.Column("source_slug", sa.String(length=100), sa.ForeignKey("data_sources.slug"), nullable=False),
        sa.Column("geography_type", sa.String(length=32), nullable=False),
        sa.Column("geoid", sa.String(length=32), nullable=False),
        sa.Column("metric", sa.String(length=120), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("vintage", sa.String(length=50), nullable=False),
        sa.Column("margin_of_error", sa.Numeric(20, 6), nullable=True),
        sa.Column("suppressed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "dataset_slug", "source_slug", "geography_type", "geoid", "metric",
            "period_start", "period_end", "vintage",
            name="uq_indicator_observations_natural",
        ),
        sa.CheckConstraint("period_end >= period_start", name="ck_indicator_observations_period"),
        sa.CheckConstraint("margin_of_error IS NULL OR margin_of_error >= 0", name="ck_indicator_observations_moe"),
    )
    op.create_index(
        "ix_indicator_observations_lookup",
        "indicator_observations",
        ["dataset_slug", "metric", "geoid", "period_end"],
    )
    op.create_table(
        "listing_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_record_id", sa.BigInteger(), sa.ForeignKey("source_records.id"), nullable=False),
        sa.Column("source_slug", sa.String(length=100), sa.ForeignKey("data_sources.slug"), nullable=False),
        sa.Column("listing_type", sa.String(length=12), nullable=False),
        sa.Column("source_listing_id", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("zip_code", sa.String(length=10), nullable=True),
        sa.Column("county_fips", sa.String(length=5), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("asking_price", sa.Numeric(16, 2), nullable=True),
        sa.Column("bedrooms", sa.Numeric(5, 1), nullable=True),
        sa.Column("bathrooms", sa.Numeric(5, 1), nullable=True),
        sa.Column("square_feet", sa.Integer(), nullable=True),
        sa.Column("property_type", sa.String(length=100), nullable=True),
        sa.Column("listed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_slug", "listing_type", "source_listing_id", name="uq_listing_records_source_listing"),
        sa.CheckConstraint("listing_type IN ('sale', 'rental')", name="ck_listing_records_type"),
        sa.CheckConstraint("asking_price IS NULL OR asking_price >= 0", name="ck_listing_records_price"),
    )
    op.create_table(
        "spatial_features",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_record_id", sa.BigInteger(), sa.ForeignKey("source_records.id"), nullable=False),
        sa.Column("dataset_slug", sa.String(length=100), sa.ForeignKey("catalog_datasets.slug"), nullable=False),
        sa.Column("source_slug", sa.String(length=100), sa.ForeignKey("data_sources.slug"), nullable=False),
        sa.Column("source_layer", sa.String(length=200), nullable=False),
        sa.Column("source_feature_id", sa.String(length=200), nullable=False),
        sa.Column("feature_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=True),
        sa.Column("jurisdiction", sa.String(length=200), nullable=True),
        sa.Column("geometry", sa.JSON(), nullable=True),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_slug", "source_layer", "source_feature_id", name="uq_spatial_features_source_feature"),
    )


def downgrade() -> None:
    op.drop_table("spatial_features")
    op.drop_table("listing_records")
    op.drop_index("ix_indicator_observations_lookup", table_name="indicator_observations")
    op.drop_table("indicator_observations")
    op.drop_index("ix_property_records_county", table_name="property_records")
    op.drop_table("property_records")
    op.drop_index("ix_source_records_source_key", table_name="source_records")
    op.drop_table("source_records")
    op.drop_index("ix_ingestion_runs_prefect_flow_run_id", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_dataset_source_started", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_index("ix_geographies_parent_id", table_name="geographies")
    op.drop_table("geographies")
    op.drop_table("dataset_sources")
    op.drop_table("data_sources")
    op.drop_table("catalog_datasets")
