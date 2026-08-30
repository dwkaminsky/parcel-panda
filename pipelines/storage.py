from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, create_engine, select, update
from sqlalchemy.dialects.postgresql import insert

from backend.models import (
    CatalogDataset,
    DataSource,
    DatasetSource,
    IndicatorObservation,
    IngestionRun,
    ListingRecord,
    PropertyRecord,
    SourceRecord,
    SpatialFeature,
)
from pipelines.catalog import DATASETS, DATASET_SOURCES, SOURCES
from pipelines.config import RunOptions
from pipelines.contracts import ExtractedBatch, LoadSummary, NormalizedRecord, RecordKind


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _sqlalchemy_url(url: str) -> str:
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _updatable_values(
    values: dict[str, Any],
    immutable_keys: set[str],
) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key not in immutable_keys}


class PipelineRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def bootstrap_catalog(self) -> None:
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            for dataset in DATASETS:
                statement = insert(CatalogDataset).values(**dataset, updated_at=now)
                connection.execute(
                    statement.on_conflict_do_update(
                        index_elements=[CatalogDataset.slug],
                        set_={
                            "name": statement.excluded.name,
                            "category": statement.excluded.category,
                            "status": statement.excluded.status,
                            "geography_grain": statement.excluded.geography_grain,
                            "cadence": statement.excluded.cadence,
                            "updated_at": now,
                        },
                    )
                )
            for source in SOURCES:
                statement = insert(DataSource).values(**source, enabled=True, updated_at=now)
                connection.execute(
                    statement.on_conflict_do_update(
                        index_elements=[DataSource.slug],
                        set_={
                            "name": statement.excluded.name,
                            "publisher": statement.excluded.publisher,
                            "source_url": statement.excluded.source_url,
                            "access_type": statement.excluded.access_type,
                            "credential_env_var": statement.excluded.credential_env_var,
                            "updated_at": now,
                        },
                    )
                )
            for dataset_slug, source_slug in DATASET_SOURCES:
                connection.execute(
                    insert(DatasetSource)
                    .values(dataset_slug=dataset_slug, source_slug=source_slug)
                    .on_conflict_do_nothing()
                )

    def create_run(
        self,
        batch: ExtractedBatch,
        options: RunOptions,
        prefect_flow_run_id: UUID | None,
    ) -> UUID:
        run_id = uuid4()
        with self.engine.begin() as connection:
            connection.execute(
                insert(IngestionRun).values(
                    id=run_id,
                    dataset_slug=batch.dataset_slug,
                    source_slug=batch.source_slug,
                    prefect_flow_run_id=prefect_flow_run_id,
                    status="running",
                    started_at=datetime.now(timezone.utc),
                    parameters=_json_safe(options.model_dump(mode="json")),
                    source_version=batch.source_version,
                    extracted_count=len(batch.records),
                    loaded_count=0,
                    unchanged_count=0,
                    error_count=0,
                )
            )
        return run_id

    def finish_run(
        self,
        run_id: UUID,
        *,
        status: str,
        loaded: int,
        unchanged: int,
        errors: int,
        error_summary: str | None = None,
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                update(IngestionRun)
                .where(IngestionRun.id == run_id)
                .values(
                    status=status,
                    finished_at=datetime.now(timezone.utc),
                    loaded_count=loaded,
                    unchanged_count=unchanged,
                    error_count=errors,
                    error_summary=error_summary,
                )
            )

    def ingest_batch(
        self,
        batch: ExtractedBatch,
        options: RunOptions,
        prefect_flow_run_id: UUID | None = None,
    ) -> LoadSummary:
        self.bootstrap_catalog()
        run_id = self.create_run(batch, options, prefect_flow_run_id)
        loaded = 0
        unchanged = 0
        try:
            with self.engine.begin() as connection:
                for record in batch.records:
                    source_record_id, created = self._source_record(
                        connection,
                        batch,
                        record,
                        run_id,
                        include_raw_payload=options.include_raw_payloads,
                    )
                    if not created:
                        unchanged += 1
                        continue
                    self._upsert_domain_record(
                        connection,
                        batch,
                        record,
                        source_record_id,
                    )
                    loaded += 1
            self.finish_run(
                run_id,
                status="succeeded",
                loaded=loaded,
                unchanged=unchanged,
                errors=0,
            )
        except Exception as exc:
            self.finish_run(
                run_id,
                status="failed",
                loaded=0,
                unchanged=0,
                errors=1,
                error_summary=str(exc)[:2_000],
            )
            raise
        return LoadSummary(
            dataset_slug=batch.dataset_slug,
            source_slug=batch.source_slug,
            extracted=len(batch.records),
            loaded=loaded,
            unchanged=unchanged,
            dry_run=False,
            skipped_reason=batch.skipped_reason,
        )

    def _source_record(
        self,
        connection,
        batch: ExtractedBatch,
        record: NormalizedRecord,
        run_id: UUID,
        *,
        include_raw_payload: bool,
    ) -> tuple[int, bool]:
        statement = (
            insert(SourceRecord)
            .values(
                source_slug=batch.source_slug,
                source_key=record.source_key,
                content_hash=record.content_hash,
                ingestion_run_id=run_id,
                retrieved_at=batch.retrieved_at,
                source_modified_at=record.source_modified_at,
                raw_payload=_json_safe(record.raw_payload) if include_raw_payload else None,
            )
            .on_conflict_do_nothing()
            .returning(SourceRecord.id)
        )
        source_record_id = connection.scalar(statement)
        if source_record_id is not None:
            return int(source_record_id), True
        existing = connection.scalar(
            select(SourceRecord.id).where(
                SourceRecord.source_slug == batch.source_slug,
                SourceRecord.source_key == record.source_key,
                SourceRecord.content_hash == record.content_hash,
            )
        )
        if existing is None:
            raise RuntimeError("source record conflict could not be resolved")
        return int(existing), False

    def _upsert_domain_record(
        self,
        connection,
        batch: ExtractedBatch,
        record: NormalizedRecord,
        source_record_id: int,
    ) -> None:
        now = datetime.now(timezone.utc)
        if record.kind == RecordKind.PROPERTY:
            values = {
                **record.data,
                "source_record_id": source_record_id,
                "source_slug": batch.source_slug,
                "updated_at": now,
            }
            values.update(
                acreage=_decimal(values.get("acreage")),
                land_value=_decimal(values.get("land_value")),
                building_value=_decimal(values.get("building_value")),
                assessed_value=_decimal(values.get("assessed_value")),
                geometry=_json_safe(values.get("geometry")),
            )
            statement = insert(PropertyRecord).values(**values)
            connection.execute(
                statement.on_conflict_do_update(
                    constraint="uq_property_records_source_parcel",
                    set_=_updatable_values(
                        values,
                        {"source_slug", "county_fips", "parcel_id"},
                    ),
                )
            )
            return
        if record.kind == RecordKind.INDICATOR:
            values = {
                **record.data,
                "source_record_id": source_record_id,
                "dataset_slug": batch.dataset_slug,
                "source_slug": batch.source_slug,
                "value": _decimal(record.data.get("value")),
                "margin_of_error": _decimal(record.data.get("margin_of_error")),
                "updated_at": now,
            }
            statement = insert(IndicatorObservation).values(**values)
            connection.execute(
                statement.on_conflict_do_update(
                    constraint="uq_indicator_observations_natural",
                    set_={
                        "source_record_id": source_record_id,
                        "value": statement.excluded.value,
                        "margin_of_error": statement.excluded.margin_of_error,
                        "suppressed": statement.excluded.suppressed,
                        "unit": statement.excluded.unit,
                        "updated_at": now,
                    },
                )
            )
            return
        if record.kind == RecordKind.LISTING:
            values = {
                **record.data,
                "source_record_id": source_record_id,
                "source_slug": batch.source_slug,
                "asking_price": _decimal(record.data.get("asking_price")),
                "bedrooms": _decimal(record.data.get("bedrooms")),
                "bathrooms": _decimal(record.data.get("bathrooms")),
                "listed_at": _datetime(record.data.get("listed_at")),
                "last_seen_at": _datetime(record.data.get("last_seen_at")),
                "updated_at": now,
            }
            statement = insert(ListingRecord).values(**values)
            connection.execute(
                statement.on_conflict_do_update(
                    constraint="uq_listing_records_source_listing",
                    set_=_updatable_values(
                        values,
                        {"source_slug", "listing_type", "source_listing_id"},
                    ),
                )
            )
            return
        if record.kind == RecordKind.SPATIAL:
            values = {
                **record.data,
                "source_record_id": source_record_id,
                "dataset_slug": batch.dataset_slug,
                "source_slug": batch.source_slug,
                "geometry": _json_safe(record.data.get("geometry")),
                "properties": _json_safe(record.data.get("properties", {})),
                "updated_at": now,
            }
            statement = insert(SpatialFeature).values(**values)
            connection.execute(
                statement.on_conflict_do_update(
                    constraint="uq_spatial_features_source_feature",
                    set_=_updatable_values(
                        values,
                        {"source_slug", "source_layer", "source_feature_id"},
                    ),
                )
            )
            return
        raise ValueError(f"Unsupported record kind: {record.kind}")


def make_repository(database_url: str) -> PipelineRepository:
    return PipelineRepository(
        create_engine(
            _sqlalchemy_url(database_url),
            pool_pre_ping=True,
        )
    )


def make_repository_from_env() -> PipelineRepository:
    database_url = os.environ.get("DATABASE_URL_DIRECT")
    if not database_url:
        raise RuntimeError("DATABASE_URL_DIRECT is required for snapshot publishing")
    if "-pooler" in database_url:
        raise RuntimeError("Pipeline writes require a direct Neon connection, not a pooled URL")
    return make_repository(database_url)
