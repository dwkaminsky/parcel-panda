from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from prefect.context import get_run_context

from pipelines.config import DatasetId, RunOptions
from pipelines.contracts import (
    CatalogRunSummary,
    ExtractedBatch,
    LoadedSnapshot,
    LocalCollectionSummary,
    LoadSummary,
)
from pipelines.local_snapshot import load_snapshot, save_snapshot
from pipelines.sources import (
    CensusACS5Adapter,
    CFPBMortgagePerformanceAdapter,
    CharlotteZoningAdapter,
    NCEMFloodAdapter,
    NCDORPropertyTaxAdapter,
    NCOneMapAssessedValueAdapter,
    NCOneMapOwnershipAdapter,
    NCOneMapParcelAdapter,
    NYFedHouseholdDebtAdapter,
    RentCastRentalAdapter,
    RentCastSaleAdapter,
)
from pipelines.sources.base import SourceAdapter


AdapterFactory = Callable[[], SourceAdapter]
AdapterKey = tuple[str, str]

ADAPTER_FACTORIES: dict[AdapterKey, AdapterFactory] = {
    (DatasetId.PARCEL_RECORDS, "nc-onemap-parcels"): NCOneMapParcelAdapter,
    (DatasetId.OWNERSHIP_BOUNDARIES, "nc-onemap-parcels"): NCOneMapOwnershipAdapter,
    (DatasetId.PROPERTY_TAX, "nc-onemap-parcels"): NCOneMapAssessedValueAdapter,
    (DatasetId.PROPERTY_TAX, "ncdor-property-tax"): NCDORPropertyTaxAdapter,
    (DatasetId.MORTGAGE, "cfpb-mortgage-performance"): CFPBMortgagePerformanceAdapter,
    (DatasetId.MORTGAGE, "nyfed-household-debt"): NYFedHouseholdDebtAdapter,
    (DatasetId.SALE_LISTINGS, "rentcast-sale"): RentCastSaleAdapter,
    (DatasetId.RENTAL_LISTINGS, "rentcast-rental"): RentCastRentalAdapter,
    (DatasetId.HOUSING_DEMOGRAPHICS, "census-acs5"): CensusACS5Adapter,
    (DatasetId.FLOOD_HAZARDS, "ncem-fris"): NCEMFloodAdapter,
    (DatasetId.ZONING, "charlotte-zoning"): CharlotteZoningAdapter,
}


def selected_adapter_keys(options: RunOptions) -> list[AdapterKey]:
    selected = {dataset.value for dataset in options.datasets}
    return [key for key in ADAPTER_FACTORIES if key[0] in selected]


@task(
    name="extract-source",
    retries=2,
    retry_delay_seconds=[5, 20],
    cache_policy=NO_CACHE,
    persist_result=False,
)
def extract_source(key: AdapterKey, options: RunOptions) -> ExtractedBatch:
    adapter = ADAPTER_FACTORIES[key]()
    batch = adapter.extract(options)
    if (batch.dataset_slug, batch.source_slug) != key:
        raise ValueError(
            f"Adapter {type(adapter).__name__} returned "
            f"{batch.dataset_slug}/{batch.source_slug}, expected {key[0]}/{key[1]}"
        )
    return batch


@task(
    name="save-local-snapshot",
    cache_policy=NO_CACHE,
    persist_result=False,
)
def save_local_snapshot(
    batches: list[ExtractedBatch],
    options: RunOptions,
    output_root: str | Path,
) -> LocalCollectionSummary:
    return save_snapshot(batches, options, output_root)


@task(
    name="read-local-snapshot",
    cache_policy=NO_CACHE,
    persist_result=False,
)
def read_local_snapshot(snapshot: str | Path) -> LoadedSnapshot:
    return load_snapshot(snapshot)


@task(
    name="publish-source",
    retries=2,
    retry_delay_seconds=[2, 10],
    cache_policy=NO_CACHE,
    persist_result=False,
)
def publish_source(
    batch: ExtractedBatch,
    options: RunOptions,
    prefect_flow_run_id: UUID | None,
) -> LoadSummary:
    from pipelines.storage import make_repository_from_env

    return make_repository_from_env().ingest_batch(
        batch,
        options,
        prefect_flow_run_id=prefect_flow_run_id,
    )


@flow(name="collect-property-data", log_prints=True)
def collect_catalog(
    options: RunOptions | dict,
    output_root: str | Path = "pipelines/data/runs",
) -> LocalCollectionSummary:
    """Extract selected NC sources into a local, publishable snapshot."""
    validated_options = RunOptions.model_validate(options).model_copy(
        update={"dry_run": True}
    )
    extraction_futures = [
        extract_source.with_options(name=f"extract-{source_slug}").submit(
            (dataset_slug, source_slug),
            validated_options,
        )
        for dataset_slug, source_slug in selected_adapter_keys(validated_options)
    ]

    batches: list[ExtractedBatch] = []
    for future in extraction_futures:
        batch = future.result()
        for warning in batch.warnings:
            print(f"{batch.source_slug}: {warning}")
        batches.append(batch)
    return save_local_snapshot(batches, validated_options, output_root)


@flow(name="publish-property-data", log_prints=True)
def publish_catalog(snapshot: str | Path) -> CatalogRunSummary:
    """Verify and publish a previously collected local snapshot idempotently."""
    loaded_snapshot = read_local_snapshot(snapshot)
    options = RunOptions.model_validate(loaded_snapshot.manifest.options).model_copy(
        update={"dry_run": False}
    )
    context = get_run_context()
    flow_run_id = context.flow_run.id if context.flow_run else None

    summaries = [
        publish_source(batch, options, flow_run_id)
        for batch in loaded_snapshot.batches
    ]

    return CatalogRunSummary(
        datasets_requested=len({batch.dataset_slug for batch in loaded_snapshot.batches}),
        batches=summaries,
        dry_run=False,
    )
